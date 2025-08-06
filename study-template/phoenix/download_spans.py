import os

import dotenv
import phoenix as px
# OpenAI SDK + instrumentation
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


@tracer.chain
def my_func(input: str) -> str:
    return "output"


print(my_func("test"))

# Wait a few seconds, then run this
client = px.Client(endpoint="http://127.0.0.1:6006")
spans_df = client.get_spans_dataframe()
print(spans_df)
