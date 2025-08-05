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


#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import dotenv
from openinference.instrumentation.openai import OpenAIInstrumentor
from phoenix.otel import register

from utils.Azurellm import Azurellm
from typing import List
from openai.types.chat import ChatCompletionMessageParam
import json

from openai.types.chat import ChatCompletionAssistantMessageParam
from openinference.semconv.trace import MessageAttributes, SpanAttributes
from opentelemetry.trace import Span

# Load environment variables
dotenv.load_dotenv()

# Ensure Phoenix endpoint is set
os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")

# Configuring a Tracer
tracer_provider = register(
    project_name="llmops",
    endpoint=os.environ["PHOENIX_COLLECTOR_ENDPOINT"],
    auto_instrument=True
)
tracer = tracer_provider.get_tracer(__name__)

# Use OpenAI Instrumentor for embedding tracing
OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

# Create user query embedding
embedding = Azurellm().azure_embeddings()
user_query = "Who is under my medical?"
vector = embedding.embed_query(user_query)

# Use Span for tracing hybrid search inputs and outputs

import redis
from redisvl.index import SearchIndex
from redisvl.query import HybridQuery

dotenv.load_dotenv()
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
    ssl_cert_reqs="none",
    ssl=True
)
print(r.ping())


index_name = "question_answer"
schema = {
  "index": {
    "name": index_name,
    "prefix": index_name,
    "storage_type": "hash"
  },
  "fields": [
    {"type" : "tag", "name" : "qna_id"},
    {"type" : "tag", "name" : "clientId_ss"},
    {"type" : "tag", "name" : "description_t"},
    {"type" : "text", "name" : "metadata_s"},
    {
        "type" : "vector",
        "name" : "embedding",
        "attrs" : {
            "dims": 3072,
            "distance_metric": "cosine",
            "algorithm": "flat",
            "datatype": "float32"
        }
    }
  ],
}
index = SearchIndex.from_dict(schema, redis_client=r, validate_on_load=True)
print(index.info()['num_docs'])

# Hybrid Search with Filters
h = HybridQuery(
    text=user_query,
    text_field_name="description_t",
    text_scorer="BM25",
    vector=np.array(vector).astype(np.float32).tobytes(),
    vector_field_name="embedding",
    return_fields=['qna_id', 'description_t', 'metadata_s', 'clientId_ss'],
    alpha=0.7, # weight the vector score lower
    num_results=10,
    filter_expression=t
)
results = index.query(h)
print("Hybrid Search Results: \n")
print(json.dumps(results, indent=4))

def set_input_attrs(
    span: Span,
    messages: List[ChatCompletionMessageParam],
    prompt_template: str,
    prompt_vars: dict | str,
) -> None:
    # INPUT_VALUE shows up on the table view under the input column
    # It also shows up under the `input` tab on the span
    span.set_attribute(
        SpanAttributes.INPUT_VALUE,
        messages[-1].get("content", ""),  # get the last message for input
    )

    # LLM_INPUT_MESSAGES shows up under `input_messages` tab on the span page
    for idx, msg in enumerate(messages):
        # Set the role per message
        span.set_attribute(
            f"{SpanAttributes.LLM_INPUT_MESSAGES}.{idx}.{MessageAttributes.MESSAGE_ROLE}",
            msg["role"],
        )
        # Set the content per message
        span.set_attribute(
            f"{SpanAttributes.LLM_INPUT_MESSAGES}.{idx}.{MessageAttributes.MESSAGE_CONTENT}",
            msg.get("content", ""),
        )

def set_output_attrs(
    span: Span,
    response_message: ChatCompletionAssistantMessageParam,
) -> None:
    # OUTPUT_VALUE shows up on the table view under the output column
    # It also shows up under the `output` tab on the span
    span.set_attribute(SpanAttributes.OUTPUT_VALUE, response_message.get("content", ""))

    # This shows up under `output_messages` tab on the span page
    # This code assumes a single response
    span.set_attribute(
        f"{SpanAttributes.LLM_OUTPUT_MESSAGES}.0.{MessageAttributes.MESSAGE_ROLE}",
        response_message["role"],
    )
    span.set_attribute(
        f"{SpanAttributes.LLM_OUTPUT_MESSAGES}.0.{MessageAttributes.MESSAGE_CONTENT}",
        response_message.get("content", ""),
    )

