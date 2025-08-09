# -*- coding: utf-8 -*-
# Minimal LLM Ops: tracing, evaluation, and analysis with Phoenix + LangChain

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
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA

tracer_provider = register(
    project_name=os.environ["PHOENIX_PROJECT_NAME"],
    endpoint=os.environ["PHOENIX_COLLECTOR_ENDPOINT"],
    auto_instrument=True,
    batch=True,
    verbose=True,
)

LangChainInstrumentor(tracer_provider=tracer_provider).instrument(skip_dep_check=True)

# --- Sample Docs ---
sample_docs = [
    "You can query monitor status using the GraphQL API at /v1/graphql/monitor",
    "Delete a model using the `deleteModel` mutation in the GraphQL API",
    "Enterprise license pricing is customized. Contact Arize support.",
    "Log a prediction using the Python SDK with `log_prediction(model_id=..., features=...)`",
]
docs = [Document(page_content=txt) for txt in sample_docs]
docs = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50).split_documents(docs)

# --- Vector Store ---
embedding = OpenAIEmbeddings(model="text-embedding-3-small")
retriever = FAISS.from_documents(docs, embedding=embedding).as_retriever(search_kwargs={"k": 3})

# --- QA Chain ---
qa_chain = RetrievalQA.from_chain_type(
    llm=ChatOpenAI(model="gpt-4o-mini", temperature=0),
    retriever=retriever,
    chain_type="stuff",
    return_source_documents=True,
)

# --- Query + Collect Results ---
queries = [
    "How can I query for a monitor's status using GraphQL?",
    "How do I delete a model?",
    "How much does an enterprise license of Arize cost?",
    "How do I log a prediction using the python SDK?",
]

qa_pairs = []
for query in queries:
    output = qa_chain.invoke({"query": query})
    answer = output.get("result", output)
    qa_pairs.append({"question": query, "ground_truth": "", "answer": answer})

import phoenix as px

from phoenix.session.evaluation import get_qa_with_reference, get_retrieved_documents

client = px.Client(endpoint="http://127.0.0.1:6006", api_key=os.getenv("PHOENIX_API_KEY"))
retrieved_documents_df = get_retrieved_documents(client, project_name="llmops")
queries_df = get_qa_with_reference(client, project_name="llmops")

retrieved_documents_df.to_csv("retrieved_documents_df.csv", index=False)
queries_df.to_csv("queries_df.csv", index=False)

import pandas as pd
import uuid

retrieved_documents_df = pd.read_csv("retrieved_documents_df.csv")
queries_df = pd.read_csv("queries_df.csv")

# One span per query (reuse this for ALL evals so they correlate)
span_map = {q: str(uuid.uuid4()) for q in queries_df["input"].unique()}

# Build the doc-level eval frame from the retrieved docs
retrieved_documents_df["context.span_id"] = retrieved_documents_df["context.trace_id"].map(span_map)
queries_df["context.span_id"] = queries_df["input"].map(span_map)

import nest_asyncio

from phoenix.evals import (
    HALLUCINATION_PROMPT_RAILS_MAP,
    HALLUCINATION_PROMPT_TEMPLATE,
    QA_PROMPT_RAILS_MAP,
    QA_PROMPT_TEMPLATE,
    OpenAIModel,
    llm_classify,
)

nest_asyncio.apply()  # Speeds up OpenAI API calls

# Check if the application has any indications of hallucinations
hallucination_eval = llm_classify(
    data=queries_df,
    model=OpenAIModel(model="gpt-4o", temperature=0.0),
    template=HALLUCINATION_PROMPT_TEMPLATE,
    rails=list(HALLUCINATION_PROMPT_RAILS_MAP.values()),
    provide_explanation=True,  # Makes the LLM explain its reasoning
)
hallucination_eval["context.span_id"] = queries_df["context.span_id"]
hallucination_eval["score"] = (
        hallucination_eval.label[~hallucination_eval.label.isna()] == "factual"
).astype(int)
hallucination_eval = hallucination_eval.set_index("context.span_id")
hallucination_eval.index.name = "context.span_id"
print(hallucination_eval.iloc[0])

# Check if the application is answering questions correctly
qa_correctness_eval = llm_classify(
    data=queries_df,
    model=OpenAIModel(model="gpt-4o", temperature=0.0),
    template=QA_PROMPT_TEMPLATE,
    rails=list(QA_PROMPT_RAILS_MAP.values()),
    provide_explanation=True,  # Makes the LLM explain its reasoning
    concurrency=4,
)
qa_correctness_eval["context.span_id"] = queries_df["context.span_id"]
qa_correctness_eval["score"] = (
        qa_correctness_eval.label[~qa_correctness_eval.label.isna()] == "correct"
).astype(int)
qa_correctness_eval = qa_correctness_eval.set_index("context.span_id")
qa_correctness_eval.index.name = "context.span_id"
print(qa_correctness_eval.iloc[0])

from phoenix.trace import SpanEvaluations

# Log to Phoenix
client.log_evaluations(
    SpanEvaluations(eval_name="Hallucination", dataframe=hallucination_eval),
    SpanEvaluations(eval_name="QA Correctness", dataframe=qa_correctness_eval),
)

from phoenix.evals import (
    RAG_RELEVANCY_PROMPT_RAILS_MAP,
    RAG_RELEVANCY_PROMPT_TEMPLATE,
    OpenAIModel,
    llm_classify,
)

retrieved_documents_eval = llm_classify(
    data=retrieved_documents_df,
    model=OpenAIModel(model="gpt-4o", temperature=0.0),
    template=RAG_RELEVANCY_PROMPT_TEMPLATE,
    rails=list(RAG_RELEVANCY_PROMPT_RAILS_MAP.values()),
    provide_explanation=True,
)

retrieved_documents_eval["score"] = (
        retrieved_documents_eval.label[~retrieved_documents_eval.label.isna()] == "relevant"
).astype(int)

retrieved_documents_eval.head()

from phoenix.trace import DocumentEvaluations

client.log_evaluations(
    DocumentEvaluations(eval_name="Relevance", dataframe=retrieved_documents_eval)
)
