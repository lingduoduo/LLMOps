# -*- coding: utf-8 -*-
# Minimal LLM Ops: tracing, evaluation, and analysis with Phoenix + LangChain

import os

import dotenv
import pandas as pd

# Load OpenAI API key
dotenv.load_dotenv()

# --- Environment Setup ---
os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")
os.environ.setdefault("PHOENIX_PROJECT_NAME", "llmops")

# --- Phoenix Tracing ---
from phoenix.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor

tracer_provider = register(
    project_name=os.environ["PHOENIX_PROJECT_NAME"],
    endpoint=os.environ["PHOENIX_COLLECTOR_ENDPOINT"],
    auto_instrument=True,
    batch=True,
    verbose=True,
)
LangChainInstrumentor(tracer_provider=tracer_provider).instrument(skip_dep_check=True)

# --- LangChain & OpenAI ---
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA

# --- Phoenix Evaluation ---
from phoenix.evals import (
    QA_PROMPT_TEMPLATE,
    QA_PROMPT_RAILS_MAP,
    HALLUCINATION_PROMPT_TEMPLATE,
    HALLUCINATION_PROMPT_RAILS_MAP,
    OpenAIModel,
    llm_classify,
)

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

    print(f"\nQuery: {query}\nResponse: {answer}")
    for i, src in enumerate(output.get("source_documents", []), 1):
        print(f"  Source {i}: {src.page_content[:120]}...")

# --- Evaluation ---
queries_df = pd.DataFrame(qa_pairs)

# Hallucination Eval
hallucination_eval = llm_classify(
    data=queries_df,
    model=OpenAIModel(model="gpt-4o", temperature=0.0),
    template=HALLUCINATION_PROMPT_TEMPLATE,
    rails=list(HALLUCINATION_PROMPT_RAILS_MAP.values()),
    provide_explanation=True,
)
hallucination_eval["score"] = (hallucination_eval.label == "factual").astype(int)

# QA Correctness Eval
qa_eval = llm_classify(
    data=queries_df,
    model=OpenAIModel(model="gpt-4o", temperature=0.0),
    template=QA_PROMPT_TEMPLATE,
    rails=list(QA_PROMPT_RAILS_MAP.values()),
    provide_explanation=True,
    concurrency=4,
)
qa_eval["score"] = (qa_eval.label == "correct").astype(int)

# --- Summary ---
print("\n=== Hallucination Evaluation ===")
print(hallucination_eval[["question", "label", "explanation", "score"]])

print("\n=== QA Correctness Evaluation ===")
print(qa_eval[["question", "label", "explanation", "score"]])
