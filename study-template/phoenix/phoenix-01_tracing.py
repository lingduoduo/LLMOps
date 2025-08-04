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
