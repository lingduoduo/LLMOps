#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
import uuid
from typing import Dict, Any, Optional, Tuple

import dotenv
import httpx
import pandas as pd

import phoenix as px
from phoenix.otel import register

from openai import AzureOpenAI
from openinference.instrumentation.openai import OpenAIInstrumentor
from openinference.semconv.trace import (
    SpanAttributes,
    OpenInferenceSpanKindValues,
)

from opentelemetry import trace as ot_trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

# -----------------------------------------------------------------------------
# 1) ENV & CONSTANTS
# -----------------------------------------------------------------------------
dotenv.load_dotenv()

PHOENIX_BASE = os.getenv("PHOENIX_BASE", "http://localhost:6006")
PHOENIX_COLLECTOR = os.getenv("PHOENIX_COLLECTOR", f"{PHOENIX_BASE}/v1/traces")
PROJECT = os.getenv("PHOENIX_PROJECT_NAME", "reporting")
PHOENIX_API_KEY = os.getenv("PHOENIX_API_KEY")

# Gateway & model
GATEWAY_ENDPOINT = os.getenv("AIGW_ENDPOINT", "https://aigateway-amrs-nonprod.oneadp.com/v0/r0")
GATEWAY_API_VERSION = os.getenv("AIGW_API_VERSION", "2023-03-15-preview")
AZURE_MODEL = os.getenv("AZURE_MODEL", "gpt-4.1-mini_2025-04-14-pgo-amrs")

# Simple pricing map in USD/token (input, output)
PRICING: Dict[str, Tuple[float, float]] = {
    # keys are just model names for simplicity
    "gpt-4o-mini": (0.00000015, 0.00000060),
    "gpt-4o":      (0.00000500, 0.00001500),
    "gpt-4.1-mini": (0.00000075, 0.00000300),  # example; adjust to your real rates
    # add your SKU names as needed
}

USER_ID = os.getenv("USER_ID", "test@example.com")
LLM_PROVIDER = "openai"  # used for attributes only

# -----------------------------------------------------------------------------
# 2) TRACING (Phoenix + OTLP)
#    - Avoid double instrumentation
#    - Use BatchSpanProcessor instead of SimpleSpanProcessor
# -----------------------------------------------------------------------------
resource = Resource.create({})
tracer_provider = register(
    project_name=PROJECT,
    endpoint=PHOENIX_COLLECTOR,
    auto_instrument=True,        # auto-instrument OpenAI via OpenInference
    batch=True,
    verbose=False,
    resource=resource,
)
# Add an explicit OTLP HTTP exporter (Phoenix also ingests this endpoint)
otlp_exporter = OTLPSpanExporter(endpoint=f"{PHOENIX_BASE}/v1/traces")
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

ot_trace.set_tracer_provider(tracer_provider)
tracer = ot_trace.get_tracer(__name__)

# OpenAI auto-instrumentation (guard against double-instrumentation)
try:
    OpenAIInstrumentor().instrument(skip_dep_check=True)
except Exception:
    # already instrumented in some environments
    pass

# -----------------------------------------------------------------------------
# 3) LLM CLIENT WITH TOKEN REFRESH + RETRIES
# -----------------------------------------------------------------------------
# Your token helper (imported) should return a short-lived token
from utils.bedrock import get_bearer_token  # noqa: E402


class GatewayLLM:
    """
    Wrapper around AzureOpenAI via AI Gateway with:
    - persistent httpx client
    - token refresh on 401
    - basic retries with exponential backoff
    """

    def __init__(self, endpoint: str, api_version: str, model: str, verify_ssl: bool = True, timeout: float = 30.0):
        self.endpoint = endpoint.rstrip("/")
        self.api_version = api_version
        self.model = model
        self.verify_ssl = verify_ssl
        self.timeout = timeout

        self._http = httpx.Client(verify=self.verify_ssl, timeout=self.timeout)
        self._client = self._build_client(get_bearer_token())

    def _build_client(self, token: str) -> AzureOpenAI:
        return AzureOpenAI(
            api_version=self.api_version,
            azure_endpoint=self.endpoint,
            api_key=token,
            http_client=self._http,
            timeout=self.timeout,
        )

    def _refresh(self):
        self._client = self._build_client(get_bearer_token())

    def chat_json(self, system_prompt: str, user_input: str, max_retries: int = 3) -> Dict[str, Any]:
        delay = 0.8
        last_exc: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input},
                    ],
                )
                # usage exists in Azure responses; attach to span outside
                content = resp.choices[0].message.content or "{}"
                return {
                    "parsed": json.loads(content),
                    "usage": getattr(resp, "usage", None),
                    "raw": resp.model_dump(),
                }
            except Exception as e:
                last_exc = e
                # naive 401 detection -> refresh token once
                if "401" in str(e) or "Unauthorized" in str(e):
                    self._refresh()
                if attempt < max_retries:
                    time.sleep(delay)
                    delay *= 2
                else:
                    break
        raise RuntimeError(f"GatewayLLM.chat_json failed after {max_retries} attempts") from last_exc


llm = GatewayLLM(
    endpoint=GATEWAY_ENDPOINT,
    api_version=GATEWAY_API_VERSION,
    model=AZURE_MODEL,
    verify_ssl=False,  # set True when your certs are configured
)

# -----------------------------------------------------------------------------
# 4) COST & CALL HELPERS
# -----------------------------------------------------------------------------
def compute_cost(model: str, prompt_toks: int, completion_toks: int) -> float:
    # Use bare model key; fall back to 0s if unknown
    in_rate, out_rate = PRICING.get(model, (0.0, 0.0))
    return prompt_toks * in_rate + completion_toks * out_rate


def traced_llm_call(user_prompt: str, user_payload_json: str) -> str:
    """
    Wraps the LLM call in a traced span and annotates with OpenInference attributes.
    """
    with tracer.start_as_current_span("reporting") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
        span.set_attribute(SpanAttributes.LLM_PROVIDER, LLM_PROVIDER)
        span.set_attribute(SpanAttributes.LLM_MODEL_NAME, AZURE_MODEL)
        span.set_attribute("user.id", USER_ID)

        # Input
        span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "application/json")
        span.set_attribute(SpanAttributes.INPUT_VALUE, user_payload_json)

        # Call LLM
        payload = json.loads(user_payload_json)
        user_input = payload.get("User Input", "")

        try:
            result = llm.chat_json(system_prompt=user_prompt, user_input=user_input)
            parsed = result["parsed"]
            usage = result.get("usage")

            # Output
            payload.update(parsed)
            output_json = json.dumps(payload)
            span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json")
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, output_json)

            # Token usage (if available)
            prompt_toks = getattr(usage, "prompt_tokens", None) or (usage or {}).get("prompt_tokens", 0)
            completion_toks = getattr(usage, "completion_tokens", None) or (usage or {}).get("completion_tokens", 0)
            total_toks = getattr(usage, "total_tokens", None) or (usage or {}).get("total_tokens", prompt_toks + completion_toks)

            span.set_attribute("llm.prompt_tokens", int(prompt_toks))
            span.set_attribute("llm.completion_tokens", int(completion_toks))
            span.set_attribute("llm.total_tokens", int(total_toks))

            # Cost
            cost = compute_cost(AZURE_MODEL, prompt_toks, completion_toks)
            span.set_attribute("llm.cost_usd", float(cost))

            # mark OK (use correct API)
            span.set_status(Status(StatusCode.OK))
            return output_json

        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            # still return something JSON-parseable
            return json.dumps({**payload, "error": str(e)})

# -----------------------------------------------------------------------------
# 5) PHOENIX CLIENT: SPANS + OPTIONAL DATASET UPLOAD
# -----------------------------------------------------------------------------
client = px.Client(endpoint=PHOENIX_BASE, api_key=PHOENIX_API_KEY)

# Pull spans for this project
spans_df = client.get_spans_dataframe(project_name=PROJECT)

# Keep only columns that exist (robust to version differences)
desired_cols = [
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
present_cols = [c for c in desired_cols if c in spans_df.columns]
spans_small = spans_df[present_cols].copy() if present_cols else spans_df.copy()

# Example rollups (guarded if columns exist)
if {"attributes.user.id", "attributes.llm.cost_usd", "span_id"}.issubset(spans_small.columns):
    by_user = (
        spans_small.groupby("attributes.user.id", dropna=False)
        .agg(total_cost_usd=("attributes.llm.cost_usd", "sum"),
             mean_latency_ms=("latency_ms", "mean") if "latency_ms" in spans_small.columns else ("span_id", "count"),
             calls=("span_id", "count"))
        .reset_index()
        .sort_values("total_cost_usd", ascending=False)
    )
else:
    by_user = pd.DataFrame()

if {"attributes.llm.model_name", "attributes.llm.cost_usd", "span_id"}.issubset(spans_small.columns):
    by_model = (
        spans_small.groupby("attributes.llm.model_name", dropna=False)
        .agg(total_cost_usd=("attributes.llm.cost_usd", "sum"),
             mean_latency_ms=("latency_ms", "mean") if "latency_ms" in spans_small.columns else ("span_id", "count"),
             calls=("span_id", "count"))
        .reset_index()
        .sort_values("total_cost_usd", ascending=False)
    )
else:
    by_model = pd.DataFrame()

# Optional: save CSVs (commented)
# run_id = uuid.uuid4().hex[:6]
# spans_small.to_csv(f"phoenix_spans_{run_id}.csv", index=False)
# if not by_user.empty: by_user.to_csv(f"phoenix_cost_by_user_{run_id}.csv", index=False)
# if not by_model.empty: by_model.to_csv(f"phoenix_cost_by_model_{run_id}.csv", index=False)

# -----------------------------------------------------------------------------
# 6) OPTIONAL: DATASET UPLOAD (VERSION-SAFE)
# -----------------------------------------------------------------------------
try:
    df = pd.DataFrame(
        [{
            "question": "What is Paul Graham known for?",
            "answer": "Co-founding Y Combinator and writing on startups and technology.",
            "metadata": {"topic": "tech"},
        }]
    )
    dataset = client.upload_dataset(
        dataframe=df,
        dataset_name="test-question_answer",
        input_keys=["question"],
        output_keys=["answer"],
        metadata_keys=["metadata"],
    )
except AttributeError:
    # Some Phoenix versions don’t have upload_dataset on Client
    dataset = None
