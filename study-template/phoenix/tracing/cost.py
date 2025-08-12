# --- requirements (conda/venv) ---
# pip install arize-phoenix arize-phoenix-otel pandas

import os
import time
import uuid
import dotenv
import pandas as pd

# Phoenix + OpenTelemetry
import phoenix as px
from phoenix.otel import register
from opentelemetry import trace
from openinference.semconv.trace import SpanAttributes, MessageAttributes

# ---------- 1) Env & constants ----------
dotenv.load_dotenv()

# Phoenix UI base (for reading spans) and OTLP/collector endpoint (for writing spans)
PHOENIX_BASE = os.getenv("PHOENIX_BASE", "http://localhost:6006")
PHOENIX_COLLECTOR = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", f"{PHOENIX_BASE}/v1/traces")
PROJECT = os.getenv("PHOENIX_PROJECT_NAME", "llmops")

# Simple model pricing map (USD/token). Replace with your real rates.
PRICING = {
    # "provider:model": (input_rate, output_rate)
    "openai:gpt-4o-mini": (0.00000015, 0.00000060),
    "openai:gpt-4o":      (0.00000500, 0.00001500),
    "anthropic:claude-3-5-sonnet": (0.00000300, 0.00001500),
}

def compute_cost(provider: str, model: str, prompt_toks: int, completion_toks: int) -> float:
    key = f"{provider}:{model}"
    in_rate, out_rate = PRICING.get(key, (0.0, 0.0))
    return prompt_toks * in_rate + completion_toks * out_rate

# ---------- 2) Phoenix tracer ----------
tracer_provider = register(
    project_name=PROJECT,
    endpoint=PHOENIX_COLLECTOR,  # e.g., "http://host:6006/v1/traces"
    auto_instrument=False,       # keep manual control; set True if you want automatic SDK hooks
    batch=True,
    verbose=False,
)
tracer = trace.get_tracer(__name__)

# ---------- 3) Wrap your LLM call with a traced span ----------
def traced_llm_call(prompt: str, provider: str, model: str, user_id: str):
    """
    Replace the simulated body with your real LLM call (OpenAI, Anthropic, Bedrock, etc.).
    The instrumentation stays the same.
    """
    start = time.time()
    with tracer.start_as_current_span("llm.request") as span:
        # Mark this as an LLM/CHAIN span in OpenInference semantics
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")

        # Basic inputs
        span.set_attribute(SpanAttributes.INPUT_VALUE, prompt)
        span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "text/plain")

        # Model metadata
        span.set_attribute(SpanAttributes.LLM_PROVIDER, provider)        # "openai", "anthropic", etc.
        span.set_attribute(SpanAttributes.LLM_MODEL_NAME, model)         # e.g., "gpt-4o-mini"
        span.set_attribute("user.id", user_id)                           # handy for rollups

        # --- Simulate an LLM call (swap with real call) ---
        time.sleep(0.2)  # simulate latency
        completion = f"Echo: {prompt[:60]}..."
        prompt_tokens = 120
        completion_tokens = 200
        # --------------------------------------------------

        # Output + token usage
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, completion)
        span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "text/plain")
        span.set_attribute("llm.prompt_tokens", prompt_tokens)
        span.set_attribute("llm.completion_tokens", completion_tokens)
        span.set_attribute("llm.total_tokens", prompt_tokens + completion_tokens)

        # Cost
        cost_usd = compute_cost(provider, model, prompt_tokens, completion_tokens)
        span.set_attribute("llm.cost_usd", cost_usd)

        # Custom business metrics (example)
        span.set_attribute("metric.pipeline", "faq-bot")
        span.set_attribute("metric.environment", "dev")

        # Child span if you want to capture rerank, embedding, etc.
        with tracer.start_as_current_span("rerank") as child:
            child.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "TOOL")
            child.set_attribute("rerank.k", 5)
            time.sleep(0.05)

    latency_ms = (time.time() - start) * 1000.0
    return {"output": completion, "latency_ms": latency_ms, "cost_usd": cost_usd}

# ---------- 4) Run a few traced calls ----------
if __name__ == "__main__":
    user = "alice@example.com"
    model = "gpt-4o-mini"
    provider = "openai"

    for q in [
        "Summarize the latest PTO policy in one paragraph.",
        "Draft a friendly reminder about tomorrow’s standup.",
        "List 3 ways to reduce S3 costs for archival data."
    ]:
        res = traced_llm_call(q, provider, model, user)
        print(f"{q[:28]!r} -> latency={res['latency_ms']:.1f}ms cost=${res['cost_usd']:.6f}")

    # Give the batch exporter a moment to flush (only needed in short-lived scripts)
    time.sleep(1.5)

    # ---------- 5) Download spans from Phoenix UI into a DataFrame ----------
    client = px.Client(endpoint=PHOENIX_BASE)  # e.g., "http://localhost:6006"
    spans_df = client.get_spans_dataframe(project_name=PROJECT)

    # Keep only a few columns you care about (adjust as needed)
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
    # Some columns may not exist if not set—use intersection
    cols = [c for c in cols if c in spans_df.columns]
    spans_small = spans_df[cols].copy()

    # Quick cost and latency rollups
    by_user = (
        spans_small.groupby("attributes.user.id", dropna=False)
        .agg(total_cost_usd=("attributes.llm.cost_usd", "sum"),
             mean_latency_ms=("latency_ms", "mean"),
             calls=("span_id", "count"))
        .reset_index()
        .sort_values("total_cost_usd", ascending=False)
    )

    by_model = (
        spans_small.groupby("attributes.llm.model_name", dropna=False)
        .agg(total_cost_usd=("attributes.llm.cost_usd", "sum"),
             mean_latency_ms=("latency_ms", "mean"),
             calls=("span_id", "count"))
        .reset_index()
        .sort_values("total_cost_usd", ascending=False)
    )

    # Save to CSV for reporting
    run_id = uuid.uuid4().hex[:6]
    spans_path = f"phoenix_spans_{run_id}.csv"
    by_user_path = f"phoenix_cost_by_user_{run_id}.csv"
    by_model_path = f"phoenix_cost_by_model_{run_id}.csv"

    spans_small.to_csv(spans_path, index=False)
    by_user.to_csv(by_user_path, index=False)
    by_model.to_csv(by_model_path, index=False)

    print(f"\nSaved:\n- {spans_path}\n- {by_user_path}\n- {by_model_path}")
