# Install dependencies if needed
# %pip install -Uqq arize-phoenix langchain langchain-openai chromadb nest_asyncio

import os
from getpass import getpass
from tqdm import tqdm
import nest_asyncio
import pandas as pd
import numpy as np

# Phoenix + OpenTelemetry setup
import phoenix as px
from phoenix.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor

# LangChain + OpenAI
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.text_splitter import CharacterTextSplitter
from langchain.document_loaders import TextLoader
from langchain.schema import Document

# API Key setup
openai_api_key = os.getenv("OPENAI_API_KEY") or getpass("🔑 Enter your OpenAI API key: ")
os.environ["OPENAI_API_KEY"] = openai_api_key

# Register Phoenix
tracer_provider = register(endpoint="http://127.0.0.1:6006/v1/traces")
LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
px.launch_app().view()
print("Phoenix UI:", px.active_session().url)

# -----------------------------
# Load documents and create a retriever
# -----------------------------

# Example: load from raw text (or replace with your own docs)
sample_docs = [
    Document(page_content="You can query monitor status using the GraphQL API at /v1/graphql/monitor"),
    Document(page_content="Delete a model using the `deleteModel` mutation in the GraphQL API"),
    Document(page_content="Enterprise license pricing is customized. Contact Arize support."),
    Document(page_content="Log a prediction using the Python SDK with `log_prediction(model_id=..., features=...)`")
]

text_splitter = CharacterTextSplitter(chunk_size=300, chunk_overlap=50)
docs = text_splitter.split_documents(sample_docs)

embedding_model = OpenAIEmbeddings(model="text-embedding-ada-002")
vectorstore = Chroma.from_documents(documents=docs, embedding=embedding_model)
retriever = vectorstore.as_retriever()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)

# -----------------------------
# Run queries
# -----------------------------

queries = [
    "How can I query for a monitor's status using GraphQL?",
    "How do I delete a model?",
    "How much does an enterprise license of Arize cost?",
    "How do I log a prediction using the python SDK?",
]

for query in tqdm(queries):
    result = qa_chain.run(query)
    print(f"\nQuery: {query}\nResponse: {result}")

# -----------------------------
# Phoenix Evaluation
# -----------------------------

from phoenix.session.evaluation import get_qa_with_reference
from phoenix.evals import (
    HALLUCINATION_PROMPT_TEMPLATE, HALLUCINATION_PROMPT_RAILS_MAP,
    QA_PROMPT_TEMPLATE, QA_PROMPT_RAILS_MAP,
    OpenAIModel, llm_classify
)
from phoenix.trace import SpanEvaluations

nest_asyncio.apply()

queries_df = get_qa_with_reference(px.active_session())
model = OpenAIModel(model="gpt-4o", temperature=0.0)

# Evaluate hallucinations
hallucination_eval = llm_classify(
    data=queries_df,
    model=model,
    template=HALLUCINATION_PROMPT_TEMPLATE,
    rails=list(HALLUCINATION_PROMPT_RAILS_MAP.values()),
    provide_explanation=True,
)
hallucination_eval["score"] = (hallucination_eval.label == "factual").astype(int)

# Evaluate QA correctness
qa_correctness_eval = llm_classify(
    data=queries_df,
    model=model,
    template=QA_PROMPT_TEMPLATE,
    rails=list(QA_PROMPT_RAILS_MAP.values()),
    provide_explanation=True,
    concurrency=4,
)
qa_correctness_eval["score"] = (qa_correctness_eval.label == "correct").astype(int)

# Log results
px.Client().log_evaluations(
    SpanEvaluations(eval_name="Hallucination", dataframe=hallucination_eval),
    SpanEvaluations(eval_name="QA Correctness", dataframe=qa_correctness_eval),
)

print("Phoenix UI (Post-Eval):", px.active_session().url)
