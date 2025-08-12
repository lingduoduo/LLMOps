#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import dotenv
from openinference.instrumentation.openai import OpenAIInstrumentor
import phoenix as px
from phoenix.otel import register
from typing import Dict, Any
import requests
import uuid
import time
import json
from openinference.semconv.trace import SpanAttributes, MessageAttributes
from openinference.instrumentation.openai import OpenAIInstrumentor
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

from utils.bedrock import get_bearer_token
import httpx
from openai import AzureOpenAI

import opentelemetry
from opentelemetry import trace as trace_api
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import Status, StatusCode


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
    resource=resource
)
span_exporter = OTLPSpanExporter(endpoint="http://localhost:6006/v1/traces")
span_processor = SimpleSpanProcessor(span_exporter=span_exporter)
tracer_provider.add_span_processor(span_processor=span_processor)
trace_api.set_tracer_provider(tracer_provider=tracer_provider)
tracer = trace_api.get_tracer(__name__)

OpenAIInstrumentor().instrument(skip_dep_check=True)

# Simple model pricing map (USD/token). Replace with your real rates.
PRICING = {
    "openai:gpt-4o-mini": (0.00000015, 0.00000060),
    "openai:gpt-4o":      (0.00000500, 0.00001500),
}

user = "test@example.com"
provider = "openai"
model = "openai:gpt-4o"

def compute_cost(provider: str, model: str, prompt_toks: int, completion_toks: int) -> float:
    key = f"{provider}:{model}"
    in_rate, out_rate = PRICING.get(key, (0.0, 0.0))
    return prompt_toks * in_rate + completion_toks * out_rate

def call_openai_api(user_prompt: str, user_input: str) -> dict:
    token = get_bearer_token()
    httpx_client = httpx.Client(verify=False)
    llm_client = AzureOpenAI(
        api_version="2023-03-15-preview",
        azure_endpoint="https://aigateway-amrs-nonprod.oneadp.com/v0/r0",
        api_key=token,
        http_client=httpx_client,
        timeout=30
    )
    try:
        response = llm_client.chat.completions.create(
            model='gpt-4.1-mini_2025-04-14-pgo-amrs',
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": user_prompt},
                {"role": "user", "content": user_input},
            ],
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return {}

def traced_llm_call(user_prompt: str, user_payload_json: str, tracer: opentelemetry.sdk.trace.Tracer):
    """
    Replace the simulated body with your real LLM call (OpenAI, Anthropic, Bedrock, etc.).
    The instrumentation stays the same.
    """
    with tracer.start_as_current_span("reporting") as span:
        user_payload_dict = json.loads(user_payload_json)
        user_input = user_payload_dict.get("User Input", "")
        response_dict = call_openai_api(user_prompt, user_input)
        user_payload_dict.update(response_dict)
        # Mark this as an LLM/CHAIN span in OpenInference semantics
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
        span.set_status(trace_api.StatusCode.OK)
        return json.dumps(user_payload_dict)

# def run_llm_app(row_json: str, customer_intent_prompt: str, tracer: opentelemetry.sdk.trace.Tracer) -> dict:
#     start = time.time()
#     with tracer.start_as_current_span("User Session") as span:
#         # Basic inputs
#         span.set_attribute(SpanAttributes.INPUT_VALUE, prompt)
#         span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "text/plain")
#
#         # Model metadata
#         span.set_attribute(SpanAttributes.LLM_PROVIDER, provider)
#         span.set_attribute(SpanAttributes.LLM_MODEL_NAME, model)
#         span.set_attribute("user.id", user_id)
#
#         # --- Simulate an LLM call (swap with real call) ---
#         completion = f"Echo: {prompt[:60]}..."
#         prompt_tokens = 120
#         completion_tokens = 200
#
#         # Output + token usage
#         span.set_attribute(SpanAttributes.OUTPUT_VALUE, completion)
#         span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "text/plain")
#         span.set_attribute("llm.prompt_tokens", prompt_tokens)
#         span.set_attribute("llm.completion_tokens", completion_tokens)
#         span.set_attribute("llm.total_tokens", prompt_tokens + completion_tokens)
#
#         # Cost
#         cost_usd = compute_cost(provider, model, prompt_tokens, completion_tokens)
#         span.set_attribute("llm.cost_usd", cost_usd)
#
#         # Custom business metrics (example)
#         span.set_attribute("metric.pipeline", "faq-bot")
#         span.set_attribute("metric.environment", "dev")
#
#         # Child span if you want to capture rerank, embedding, etc.
#         with tracer.start_as_current_span("rerank") as child:
#             child.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "TOOL")
#             child.set_attribute("rerank.k", 5)
#
#     latency_ms = (time.time() - start) * 1000.0
#     return {"output": completion, "latency_ms": latency_ms, "cost_usd": cost_usd}
#
# for q in [
#     "hi! im Bob",
#     "what's my name?",
#     "Who is covered under my benefits?"
# ]:
#     res = traced_llm_call(q, provider, model, user)
#     print(f"{q[:28]!r} -> latency={res['latency_ms']:.1f}ms cost=${res['cost_usd']:.6f}")
#

# Download spans from Phoenix UI into a DataFrame
client = px.Client(endpoint=PHOENIX_BASE, api_key=os.getenv("PHOENIX_API_KEY"))
spans_df = client.get_spans_dataframe(project_name=PROJECT)

# Keep only a few columns you care about (adjust as needed)
# cols = [
#     "span_id",
#     "name",
#     "start_time",
#     "end_time",
#     "attributes.llm.model_name",
#     "attributes.llm.provider",
#     "attributes.llm.prompt_tokens",
#     "attributes.llm.completion_tokens",
#     "attributes.llm.cost_usd",
#     "attributes.metric.pipeline",
#     "attributes.user.id",
#     "latency_ms",
# ]
# # Some columns may not exist if not set—use intersection
# cols = [c for c in cols if c in spans_df.columns]
# spans_small = spans_df[cols].copy()
# print(spans_small.iloc[0])

# # Quick cost and latency rollups
# by_user = (
#     spans_small.groupby("attributes.user.id", dropna=False)
#     .agg(total_cost_usd=("attributes.llm.cost_usd", "sum"),
#          mean_latency_ms=("latency_ms", "mean"),
#          calls=("span_id", "count"))
#     .reset_index()
#     .sort_values("total_cost_usd", ascending=False)
# )
#
# by_model = (
#     spans_small.groupby("attributes.llm.model_name", dropna=False)
#     .agg(total_cost_usd=("attributes.llm.cost_usd", "sum"),
#          mean_latency_ms=("latency_ms", "mean"),
#          calls=("span_id", "count"))
#     .reset_index()
#     .sort_values("total_cost_usd", ascending=False)
# )
#
# # Save to CSV for reporting
# run_id = uuid.uuid4().hex[:6]
# spans_path = f"phoenix_spans_{run_id}.csv"
# by_user_path = f"phoenix_cost_by_user_{run_id}.csv"
# by_model_path = f"phoenix_cost_by_model_{run_id}.csv"
#
# spans_small.to_csv(spans_path, index=False)
# by_user.to_csv(by_user_path, index=False)
# by_model.to_csv(by_model_path, index=False)
#
# print(f"\nSaved:\n- {spans_path}\n- {by_user_path}\n- {by_model_path}")


# Test upload datasets
import pandas as pd
df = pd.DataFrame(
    [
        {
            "question": "What is Paul Graham known for?",
            "answer": "Co-founding Y Combinator and writing on startups and technology.",
            "metadata": {"topic": "tech"},
        }
    ]
)
dataset = client.upload_dataset(
    dataframe=df,
    dataset_name="test-question_answer",
    input_keys=["question"],
    output_keys=["answer"],
    metadata_keys=["metadata"],
)
