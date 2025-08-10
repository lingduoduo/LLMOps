import os

import dotenv

# Load OpenAI API key
dotenv.load_dotenv()

# --- Environment Setup ---
os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")
os.environ.setdefault("PHOENIX_PROJECT_NAME", "llmops")

# # --- Phoenix Tracing ---
from phoenix.otel import register

from openinference.instrumentation.langchain import LangChainInstrumentor
# --- LangChain & OpenAI ---
from langchain.chains import RetrievalQA

tracer_provider = register(
    project_name=os.environ["PHOENIX_PROJECT_NAME"],
    endpoint=os.environ["PHOENIX_COLLECTOR_ENDPOINT"],
    auto_instrument=True,
    batch=True,
    verbose=True,
)

LangChainInstrumentor(tracer_provider=tracer_provider).instrument(skip_dep_check=True)
