import os
import time
import uuid

import dotenv
import phoenix as px
from openai import OpenAI
# OpenAI SDK + instrumentation
from openinference.instrumentation.openai import OpenAIInstrumentor
from openinference.semconv.trace import SpanAttributes
from opentelemetry import trace
from phoenix.otel import register

# ---------- 1) Env & constants ----------
dotenv.load_dotenv()

PHOENIX_BASE = os.getenv("PHOENIX_BASE", "http://localhost:6006")
PHOENIX_COLLECTOR = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", f"{PHOENIX_BASE}/v1/traces")
PROJECT = os.getenv("PHOENIX_PROJECT_NAME", "llmops")

# ---------- 2) Phoenix tracer ----------
tracer_provider = register(
    project_name=PROJECT,
    endpoint=PHOENIX_COLLECTOR,
    auto_instrument=True,
    batch=True,
    verbose=False,
)
tracer = tracer_provider.get_tracer(__name__)

# ---------- 3) Phoenix client (UI helpers) ----------
phoenix_client = px.Client(endpoint=PHOENIX_BASE)
print("Phoenix UI:", PHOENIX_BASE)
print("Project UI:", f"{PHOENIX_BASE}/projects/{PROJECT}")

# OpenAI instrumentation (do this once) ----------
OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

# Run inside a session span so everything groups in Phoenix ----------
session_id = str(uuid.uuid4())
print("Session ID:", session_id)
print("Session UI:", f"{PHOENIX_BASE}/projects/{PROJECT}/sessions/{session_id}")

with tracer.start_as_current_span("session", kind=trace.SpanKind.SERVER) as span:
    # Attach session id so Phoenix groups traces
    span.set_attribute(SpanAttributes.SESSION_ID, session_id)


    # Example traced function (explicit span, rather than a non-existent decorator)
    def my_func(inp: str) -> str:
        with tracer.start_as_current_span("my_func", kind=trace.SpanKind.INTERNAL) as s:
            s.set_attribute("app.input_preview", inp[:32])
            return "output"


    print(my_func("input example"))

    # Example OpenAI call (use a current model)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY in environment.")
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say this is a test"}],
        temperature=0,
    )
    print(resp.choices[0].message.content)

# ---------- 7) Ensure traces reach Phoenix before exit ----------
tracer_provider.force_flush()
time.sleep(1)  # small grace for exporter

import numpy as np
from opentelemetry.trace import get_tracer

def hybrid_search_with_tracing(user_query: str, embedding, index, tracer) -> list:
    vector = embedding.embed_query(user_query)
    results = []

    with tracer.start_as_current_span("hybrid_search") as span:
        # --- Input span attributes ---
        span.set_attribute(SpanAttributes.INPUT_VALUE, user_query)
        span.set_attribute(f"{SpanAttributes.LLM_INPUT_MESSAGES}.0.{MessageAttributes.MESSAGE_ROLE}", "user")
        span.set_attribute(f"{SpanAttributes.LLM_INPUT_MESSAGES}.0.{MessageAttributes.MESSAGE_CONTENT}", user_query)

        # Hybrid search query config
        h = HybridQuery(
            text=user_query,
            text_field_name="description_t",
            text_scorer="BM25",
            vector=np.array(vector).astype(np.float32).tobytes(),
            vector_field_name="embedding",
            return_fields=['qna_id', 'description_t', 'metadata_s', 'clientId_ss'],
            alpha=0.7,
            num_results=10,
        )

        # Run query
        results = index.query(h)

        # --- Output span attributes ---
        output_texts = []
        for i, hit in enumerate(results):
            output_text = f"[{i}] qna_id={hit.get('qna_id')} desc={hit.get('description_t')}"
            output_texts.append(output_text)
            span.set_attribute(f"{SpanAttributes.LLM_OUTPUT_MESSAGES}.{i}.{MessageAttributes.MESSAGE_ROLE}", "retrieval")
            span.set_attribute(f"{SpanAttributes.LLM_OUTPUT_MESSAGES}.{i}.{MessageAttributes.MESSAGE_CONTENT}", output_text)

        span.set_attribute(SpanAttributes.OUTPUT_VALUE, "\n".join(output_texts))

    return results


@tracer.chain
def fetch_fusion(query: str) -> Dict[str, Any]:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Trace-ID": "ling-jupyter-test",
        "X-OHCM-User-Language": "en-US",
    }
    url = (
        "https://search.fusion.lyric.app.fit2.us.caas.oneadp.com/api/apps/" 
        "lyric/query/people_4f76ca21-8350-41e8-8bc8-5f677362d9cf_query"
    )

    payload = (
        f"q={query}"
    )
    response = requests.post(url, headers=headers, data=payload, verify=False)
    results = response.json().get("response", {}).get("docs", [])
    return {"output": results}
fetch_fusion("Bob")
