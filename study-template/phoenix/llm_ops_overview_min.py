# -*- coding: utf-8 -*-
# Minimal LLM Ops: tracing, evaluation, and analysis with Phoenix + LlamaIndex

# pip installs (uncomment if needed)
# %pip install -Uqq arize-phoenix openinference-instrumentation-llama_index "openai>=1" gcsfs nest_asyncio llama-index-llms-openai llama-index-embeddings-openai

import os
from getpass import getpass

import phoenix as px
from phoenix.otel import register
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor

from gcsfs import GCSFileSystem
from llama_index.core import Settings, StorageContext, load_index_from_storage
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding

from tqdm import tqdm
import nest_asyncio

# --- Auth ---
openai_api_key = os.getenv("OPENAI_API_KEY") or getpass("🔑 Enter your OpenAI API key: ")
os.environ["OPENAI_API_KEY"] = openai_api_key

# --- Phoenix ---
px.launch_app().view()
tracer_provider = register(endpoint="http://127.0.0.1:6006/v1/traces")
LlamaIndexInstrumentor().instrument(skip_dep_check=True, tracer_provider=tracer_provider)

# --- Load index ---
fs = GCSFileSystem(project="public-assets-275721")
index_path = "arize-phoenix-assets/datasets/unstructured/llm/llama-index/arize-docs/index/"
storage_context = StorageContext.from_defaults(fs=fs, persist_dir=index_path)

Settings.llm = OpenAI(model="gpt-4o-mini")
Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")

index = load_index_from_storage(storage_context)
query_engine = index.as_query_engine()

# --- Run queries ---
queries = [
    "How can I query for a monitor's status using GraphQL?",
    "How do I delete a model?",
    "How much does an enterprise license of Arize cost?",
    "How do I log a prediction using the python SDK?",
]
for q in tqdm(queries):
    r = query_engine.query(q)
    print(f"Query: {q}\nResponse: {r}\n")

print("Phoenix UI:", px.active_session().url)

# --- Evaluations ---
from phoenix.session.evaluation import get_qa_with_reference, get_retrieved_documents
from phoenix.evals import (
    HALLUCINATION_PROMPT_TEMPLATE, HALLUCINATION_PROMPT_RAILS_MAP,
    QA_PROMPT_TEMPLATE, QA_PROMPT_RAILS_MAP,
    RAG_RELEVANCY_PROMPT_TEMPLATE, RAG_RELEVANCY_PROMPT_RAILS_MAP,
    OpenAIModel, llm_classify,
)
from phoenix.trace import SpanEvaluations, DocumentEvaluations

nest_asyncio.apply()

queries_df = get_qa_with_reference(px.active_session())
retrieved_documents_df = get_retrieved_documents(px.active_session())
eval_model = OpenAIModel(model="gpt-4o", temperature=0.0)

# Hallucination
hallucination_eval = llm_classify(
    data=queries_df,
    model=eval_model,
    template=HALLUCINATION_PROMPT_TEMPLATE,
    rails=list(HALLUCINATION_PROMPT_RAILS_MAP.values()),
    provide_explanation=True,
)
hallucination_eval["score"] = (hallucination_eval.label == "factual").astype(int)

# QA Correctness
qa_correctness_eval = llm_classify(
    data=queries_df,
    model=eval_model,
    template=QA_PROMPT_TEMPLATE,
    rails=list(QA_PROMPT_RAILS_MAP.values()),
    provide_explanation=True,
    concurrency=4,
)
qa_correctness_eval["score"] = (qa_correctness_eval.label == "correct").astype(int)

# RAG Relevancy
retrieved_documents_eval = llm_classify(
    data=retrieved_documents_df,
    model=eval_model,
    template=RAG_RELEVANCY_PROMPT_TEMPLATE,
    rails=list(RAG_RELEVANCY_PROMPT_RAILS_MAP.values()),
    provide_explanation=True,
)
retrieved_documents_eval["score"] = (retrieved_documents_eval.label == "relevant").astype(int)

# Log to Phoenix
px.Client().log_evaluations(
    SpanEvaluations(eval_name="Hallucination", dataframe=hallucination_eval),
    SpanEvaluations(eval_name="QA Correctness", dataframe=qa_correctness_eval),
    DocumentEvaluations(eval_name="Relevance", dataframe=retrieved_documents_eval),
)

print("Phoenix UI (post-eval):", px.active_session().url)
