#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import json
import dotenv
from typing import Dict, Any

from openinference.instrumentation.openai import OpenAIInstrumentor
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

import phoenix as px
from phoenix.otel import register

import httpx
from openai import AzureOpenAI

from opentelemetry import trace as trace_api
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

from utils.bedrock import get_bearer_token
import pandas as pd

# Load environment variables
dotenv.load_dotenv()

PHOENIX_BASE = "http://localhost:6006"
PHOENIX_COLLECTOR = f"{PHOENIX_BASE}/v1/traces"
PROJECT = "reporting"

# Register Phoenix tracer
resource = Resource(attributes={})
tracer_provider = register(
    project_name=PROJECT,
    endpoint=PHOENIX_COLLECTOR,
    auto_instrument=True,
    verbose=True,
    resource=resource,
)
# Prefer BatchSpanProcessor for throughput
span_exporter = OTLPSpanExporter(endpoint=f"{PHOENIX_BASE}/v1/traces")
tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
trace_api.set_tracer_provider(tracer_provider)
tracer = trace_api.get_tracer(__name__)

# OpenAI auto-instrument (guard against double instrumentation)
try:
    OpenAIInstrumentor().instrument(skip_dep_check=True)
except Exception:
    pass

# Simple model pricing map (USD/token)
PRICING: Dict[str, tuple[float, float]] = {
    "openai:gpt-4o-mini": (0.00000015, 0.00000060),
    "openai:gpt-4o":      (0.00000500, 0.00001500),
}

user = "test@example.com"
provider = "openai"
model = "openai:gpt-4o"

def _price_key(provider: str, model: str) -> str:
    return model if ":" in model else f"{provider}:{model}"

def compute_cost(provider: str, model: str, prompt_toks: int, completion_toks: int) -> float:
    in_rate, out_rate = PRICING.get(_price_key(provider, model), (0.0, 0.0))
    return prompt_toks * in_rate + completion_toks * out_rate

def _make_llm_client(token: str) -> AzureOpenAI:
    httpx_client = httpx.Client(verify=False, timeout=30)
    return AzureOpenAI(
        api_version="2023-03-15-preview",
        azure_endpoint="https://aigateway-amrs-nonprod.oneadp.com/v0/r0",
        api_key=token,
        http_client=httpx_client,
        timeout=30,
    )

def call_openai_api(user_prompt: str, user_input: str) -> dict:
    """
    Same signature; minimal reliability: retry once on 401 by refreshing token.
    """
    def _call(client: AzureOpenAI) -> dict:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini_2025-04-14-pgo-amrs",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": user_prompt},
                {"role": "user", "content": user_input},
            ],
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)

    try:
        client = _make_llm_client(get_bearer_token())
        return _call(client)
    except Exception as e:
        if "401" in str(e) or "Unauthorized" in str(e):
            try:
                client = _make_llm_client(get_bearer_token())  # refresh once
                return _call(client)
            except Exception as e2:
                print(f"Error after token refresh: {e2}")
        else:
            print(f"Error calling OpenAI API: {e}")
    return {}

def traced_llm_call(user_prompt: str, user_payload_json: str, tracer: trace_api.Tracer):
    with tracer.start_as_current_span("reporting") as span:
        user_payload_dict = json.loads(user_payload_json)
        user_input = user_payload_dict.get("User Input", "")

        response_dict = call_openai_api(user_prompt, user_input)
        user_payload_dict.update(response_dict)

        # OpenInference attrs + I/O
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
        span.set_attribute(SpanAttributes.LLM_PROVIDER, provider)
        span.set_attribute(SpanAttributes.LLM_MODEL_NAME, model)
        span.set_attribute("user.id", user)
        span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "application/json")
        span.set_attribute(SpanAttributes.INPUT_VALUE, user_payload_json)
        span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json")
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, json.dumps(user_payload_dict))

        span.set_status(Status(StatusCode.OK))
        return json.dumps(user_payload_dict)

# Download spans from Phoenix UI into a DataFrame (graceful if not available)
try:
    client = px.Client(endpoint=PHOENIX_BASE, api_key=os.getenv("PHOENIX_API_KEY"))
    spans_df = client.get_spans_dataframe(project_name=PROJECT)
except Exception as e:
    print(f"[Phoenix] Could not fetch spans: {e}")
    spans_df = pd.DataFrame()

# Test upload datasets (kept, guarded for versions without this API)
dataset = None
try:
    df = pd.DataFrame(
        [
            {
                "question": "What is Paul Graham known for?",
                "answer": "Co-founding Y Combinator and writing on startups and technology.",
                "metadata": {"topic": "tech"},
            }
        ]
    )
    if hasattr(client, "upload_dataset"):
        dataset = client.upload_dataset(
            dataframe=df,
            dataset_name="test-question_answer",
            input_keys=["question"],
            output_keys=["answer"],
            metadata_keys=["metadata"],
        )
except Exception as e:
    print(f"[Phoenix] Dataset upload skipped: {e}")

# Optional smoke test
if __name__ == "__main__":
    prompt = "You are a JSON-only assistant. Return keys: foo, bar."
    payload = json.dumps({"User Input": "Say hello in JSON."})
    out = traced_llm_call(prompt, payload, tracer)
    print("LLM output:", out)
    print("Spans shape:", getattr(spans_df, "shape", None))
    print("Dataset:", dataset)
