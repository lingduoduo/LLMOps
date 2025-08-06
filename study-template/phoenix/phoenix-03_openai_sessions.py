import os
import uuid

import dotenv
from openai import OpenAI
from openinference.instrumentation import using_session
from openinference.instrumentation.openai import OpenAIInstrumentor
from openinference.semconv.trace import SpanAttributes
from opentelemetry import trace
# OpenAI SDK + instrumentation
from phoenix.otel import register

# ---------- 1) Env & constants ----------
dotenv.load_dotenv()

PHOENIX_BASE = "http://localhost:6006"
PHOENIX_COLLECTOR = f"{PHOENIX_BASE}/v1/traces"
PROJECT = "llmops"

# ---------- 2) Phoenix tracer ----------
tracer_provider = register(
    project_name=PROJECT,
    endpoint=PHOENIX_COLLECTOR,
    auto_instrument=True,
    batch=True,
    verbose=False,
)
tracer = tracer_provider.get_tracer(__name__)
OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

session_id = str(uuid.uuid4())
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)


@tracer.start_as_current_span(
    name="agent", attributes={SpanAttributes.OPENINFERENCE_SPAN_KIND: "agent"}
)
def assistant(
        messages: list[dict],
        session_id: str,
):
    current_span = trace.get_current_span()
    current_span.set_attribute(SpanAttributes.SESSION_ID, session_id)
    current_span.set_attribute(SpanAttributes.INPUT_VALUE, messages[-1].get("content"))

    # Propagate the session_id down to spans crated by the OpenAI instrumentation
    # This is not strictly necessary, but it helps to correlate the spans to the same session
    with using_session(session_id):
        response = (
            client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system",
                           "content": "You are a helpful assistant."}] + messages,
            )
            .choices[0]
            .message
        )
    current_span.set_attribute(SpanAttributes.OUTPUT_VALUE, response.content)
    return response


messages = [{"role": "user", "content": "hi! im bob"}]
response = assistant(
    messages,
    session_id=session_id,
)
messages = messages + [response, {"role": "user", "content": "what's my name?"}]
response = assistant(
    messages,
    session_id=session_id,
)
messages = messages + [response, {"role": "user", "content": "what's 4+5?"}]
response = assistant(
    messages,
    session_id=session_id,
)
