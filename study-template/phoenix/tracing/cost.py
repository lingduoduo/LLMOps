#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import dotenv
import json
import uuid
import time
from typing import Dict

# OpenInference / OpenAI
from openinference.instrumentation.openai import OpenAIInstrumentor
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

# Phoenix
import phoenix as px
from phoenix.otel import register

# LLM client (Azure via gateway)
import httpx
from openai import AzureOpenAI

# OpenTelemetry
from opentelemetry import trace as trace_api
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import Status, StatusCode

# Token helper
from utils.bedrock import get_bearer_token

# ------------------------------------------------------------------------------
# Env
# ------------------------------------------------------------------------------
dotenv.load_dotenv()

PHOENIX_BASE = "http://localhost:6006"
PHOENIX_COLLECTOR = f"{PHOENIX_BASE}/v1/traces"
PROJECT = "reporting"

# ------------------------------------------------------------------------------
# Tracer (Phoenix)
# ------------------------------------------------------------------------------
resource = Resource(attributes={})
tracer_provider = register(
    project_name=PROJECT,
    endpoint=PHOENIX_COLLECTOR,
    auto_instrument=True,
    verbose=True,
    resource=resource,
)
span_exporter = OTLPSpanExporter(endpoint=PHOENIX_COLLECTOR)
span_processor = SimpleSpanProcessor(span_exporter)
tracer_provider.add_span_processor(span_processor)
# set tracer provider (positional arg to be safe across versions)
trace_api.set_tracer_provider(tracer_provider)
tracer = trace_api.get_tracer(__name__)

# Guard against double instrumentation in reruns
try:
    OpenAIInstrumentor().instrument(skip_dep_check=True)
except Exception:
    pass

# ------------------------------------------------------------------------------
# Pricing
# ------------------------------------------------------------------------------
PRICING: Dict[str, tuple[float, float]] = {
    "openai:gpt-4o-mini": (0.00000015, 0.00000060),
    "openai:gpt-4o":      (0.00000500, 0.00001500),
    "bedrock:sonnet35_v2": (0.000003,  0.000015),
    "bedrock:sonnet37":    (0.000003,  0.000015),
    "bedrock:nova_pro":    (8e-7,      0.0000032),
    "bedrock:nova_lite":   (6e-8,      2.4e-7),
}

# Test example metadata
user = "test@example.com"
provider = "openai"
model = "openai:gpt-4o"

def _price_key(provider: str, model: str) -> str:
    # if model already includes provider (e.g., "openai:gpt-4o"), use as-is
    return model if ":" in model else f"{provider}:{model}"

def compute_cost(provider: str, model: str, prompt_toks: int, completion_toks: int) -> float:
    in_rate, out_rate = PRICING.get(_price_key(provider, model), (0.0, 0.0))
    return prompt_toks * in_rate + completion_toks * out_rate

# ------------------------------------------------------------------------------
# LLM call (Azure via AI Gateway)
# ------------------------------------------------------------------------------
def call_openai_api(user_prompt: str, user_input: str) -> dict:
    token = get_bearer_token()
    httpx_client = httpx.Client(verify=False)
    llm_client = AzureOpenAI(
        api_version="2023-03-15-preview",
        azure_endpoint="https://aigateway-amrs-nonprod.oneadp.com/v0/r0",
        api_key=token,
        http_client=httpx_client,
        timeout=30,
    )
    try:
        response = llm_client.chat.completions.create(
            model="gpt-4.1-mini_2025-04-14-pgo-amrs",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": user_prompt},
                {"role": "user", "content": user_input},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return {}

# ------------------------------------------------------------------------------
# Traced LLM call
# ------------------------------------------------------------------------------
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

        # Correct status API
        span.set_status(Status(StatusCode.OK))
        return json.dumps(user_payload_dict)

# ------------------------------------------------------------------------------
# (Optional) Simulated session function from your sample — left here but DISABLED
# It referenced undefined variables (prompt, user_id), so keep it as a template.
# ------------------------------------------------------------------------------
# def run_llm_calls(row_json: str, customer_intent_prompt: str, tracer: trace_api.Tracer) -> dict:
#     start = time.time()
#     with tracer.start_as_current_span("User Session") as span:
#         ...
#     latency_ms = (time.time() - start) * 1000.0
#     return {"output": completion, "latency_ms": latency_ms, "cost_usd": cost_usd}

# ------------------------------------------------------------------------------
# Phoenix reporting
# ------------------------------------------------------------------------------
client = px.Client(endpoint=PHOENIX_BASE, api_key=os.getenv("PHOENIX_API_KEY"))
spans_df = client.get_spans_dataframe(project_name=PROJECT)

cols = [
    "span_id",
    "name",
    "start_time",
    "end_time",
    "attributes.llm.model_name",
    "attributes.llm.provider",
    "attributes.llm.prompt_tokens",
    "attributes.llm.completion_tokens",
    "attributes.llm.cost_usd",
    "attributes.metric.pipeline",
    "attributes.user.id",
    "latency_ms",
]
cols = [c for c in cols if c in spans_df.columns]
spans_small = spans_df[cols].copy() if cols else spans_df.copy()

if not spans_small.empty:
    print(spans_small.iloc[0])

by_user = (
    spans_small.groupby("attributes.user.id", dropna=False)
    .agg(
        total_cost_usd=("attributes.llm.cost_usd", "sum"),
        mean_latency_ms=("latency_ms", "mean") if "latency_ms" in spans_small.columns else ("span_id", "count"),
        calls=("span_id", "count"),
    )
    .reset_index()
    .sort_values("total_cost_usd", ascending=False)
)

by_model = (
    spans_small.groupby("attributes.llm.model_name", dropna=False)
    .agg(
        total_cost_usd=("attributes.llm.cost_usd", "sum"),
        mean_latency_ms=("latency_ms", "mean") if "latency_ms" in spans_small.columns else ("span_id", "count"),
        calls=("span_id", "count"),
    )
    .reset_index()
    .sort_values("total_cost_usd", ascending=False)
)

run_id = uuid.uuid4().hex[:6]
spans_path = f"phoenix_spans_{run_id}.csv"
by_user_path = f"phoenix_cost_by_user_{run_id}.csv"
by_model_path = f"phoenix_cost_by_model_{run_id}.csv"

spans_small.to_csv(spans_path, index=False)
by_user.to_csv(by_user_path, index=False)
by_model.to_csv(by_model_path, index=False)

print(f"\nSaved:\n- {spans_path}\n- {by_user_path}\n- {by_model_path}")

# ------------------------------------------------------------------------------
# Minimal smoke test (replaces the broken for-loop in the sample)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    prompt = "You are a JSON-only assistant. Return keys: foo, bar."
    payload = json.dumps({"User Input": "Say hello in JSON."})
    out_json = traced_llm_call(prompt, payload, tracer)
    print("LLM output:", out_json)
