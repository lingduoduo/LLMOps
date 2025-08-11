#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Minimal LLM Ops: tracing, evaluation, and analysis with Phoenix + LangChain
import os
import uuid
import dotenv
import pandas as pd

# --- Phoenix Tracing ---
import phoenix as px
from phoenix.otel import register
from phoenix.session.evaluation import get_qa_with_reference, get_retrieved_documents
from openinference.instrumentation.langchain import LangChainInstrumentor
# --- LangChain ---
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
# --- Azure OpenAI ---
from utils.Azurellm import Azurellm

dotenv.load_dotenv()

PHOENIX_BASE = "http://localhost:6006"
PHOENIX_COLLECTOR = f"{PHOENIX_BASE}/v1/traces"
PROJECT = "llmops"

# Register Phoenix tracer
tracer_provider = register(
    project_name=PROJECT,
    endpoint=PHOENIX_COLLECTOR,
    auto_instrument=True,
    verbose=True
)
tracer = tracer_provider.get_tracer(__name__)
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
embedding = Azurellm().azure_embeddings()
retriever = FAISS.from_documents(docs, embedding=embedding).as_retriever(search_kwargs={"k": 3})

# --- QA Chain ---
llm = Azurellm().azure_client_openai()
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
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

client = px.Client(endpoint=PHOENIX_BASE, api_key=os.getenv("PHOENIX_API_KEY"))
print("Phoenix UI:", PHOENIX_BASE)

spans_df = client.get_spans_dataframe(project_name=PROJECT)
queries_df = get_qa_with_reference(client, project_name=PROJECT)
retrieved_documents_df = get_retrieved_documents(client, project_name=PROJECT)

queries_df.to_csv("queries_df.csv", index=False)
retrieved_documents_df.to_csv("retrieved_documents_df.csv", index=False)


# --- Need to unblock OpenAIModel---
# queries_df = pd.read_csv("queries_df.csv")
# retrieved_documents_df = pd.read_csv("retrieved_documents_df.csv")
#
#
# from phoenix.evals import (
#     HallucinationEvaluator,
#     OpenAIModel,
#     QAEvaluator,
#     RelevanceEvaluator,
#     run_evals,
# )
# from phoenix.trace import DocumentEvaluations
# from phoenix.trace import SpanEvaluations
#
# eval_model = OpenAIModel(model="gpt-4", temperature=0.0)
# hallucination_evaluator = HallucinationEvaluator(eval_model)
# qa_correctness_evaluator = QAEvaluator(eval_model)
# relevance_evaluator = RelevanceEvaluator(eval_model)
#
# hallucination_eval_df, qa_correctness_eval_df = run_evals(
#     dataframe=queries_df,
#     evaluators=[hallucination_evaluator, qa_correctness_evaluator],
#     provide_explanation=True,
# )
# relevance_eval_df = run_evals(
#     dataframe=retrieved_documents_df,
#     evaluators=[relevance_evaluator],
#     provide_explanation=True,
# )[0]
#
# client.log_evaluations(
#     SpanEvaluations(eval_name="Hallucination", dataframe=hallucination_eval_df),
#     SpanEvaluations(eval_name="QA Correctness", dataframe=qa_correctness_eval_df),
#     DocumentEvaluations(eval_name="Relevance", dataframe=relevance_eval_df),
# )
