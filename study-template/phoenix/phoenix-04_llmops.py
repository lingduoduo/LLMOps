# -*- coding: utf-8 -*-
# Minimal LLM Ops: tracing, evaluation, and analysis with Phoenix + LangChain

import os

import dotenv

# Load OpenAI API key
dotenv.load_dotenv()

# --- Environment Setup ---
os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")
os.environ.setdefault("PHOENIX_PROJECT_NAME", "llmops")

# --- Phoenix Tracing ---
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

spans_df = px.Client(endpoint="http://127.0.0.1:6006").get_spans_dataframe()
print(spans_df)

queries_df = get_qa_with_reference(px.active_session())
# spans_df = px.Client().get_spans_dataframe()
# spans_df[["name", "span_kind", "attributes.input.value", "attributes.retrieval.documents"]].head()
# print(f"\nQuery: {query}\nResponse: {answer}")
# for i, src in enumerate(output.get("source_documents", []), 1):
#     print(f"  Source {i}: {src.page_content[:120]}...")

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
from phoenix.evals import (
    HallucinationEvaluator,
    OpenAIModel,
    QAEvaluator,
    RelevanceEvaluator,
    run_evals,
)
from openinference.instrumentation.langchain import LangChainInstrumentor
# --- LangChain & OpenAI ---
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA

from utils.Azurellm import Azurellm

dotenv.load_dotenv()

PHOENIX_BASE = os.getenv("PHOENIX_BASE", "http://localhost:6006")
PHOENIX_COLLECTOR = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", f"{PHOENIX_BASE}/v1/traces")
PROJECT = os.getenv("PHOENIX_PROJECT_NAME", "llmops")

# Register Phoenix tracer
tracer_provider = register(
    project_name=PROJECT,
    endpoint=PHOENIX_COLLECTOR,
    auto_instrument=True,
    verbose=True
)
tracer = tracer_provider.get_tracer(__name__)
session_id = str(uuid.uuid4())

LangChainInstrumentor(tracer_provider=tracer_provider).instrument(skip_dep_check=True)
#
# # --- Sample Docs ---
# sample_docs = [
#     "You can query monitor status using the GraphQL API at /v1/graphql/monitor",
#     "Delete a model using the `deleteModel` mutation in the GraphQL API",
#     "Enterprise license pricing is customized. Contact Arize support.",
#     "Log a prediction using the Python SDK with `log_prediction(model_id=..., features=...)`",
# ]
# docs = [Document(page_content=txt) for txt in sample_docs]
# docs = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50).split_documents(docs)
#
# # --- Vector Store ---
# embedding = Azurellm().azure_embeddings()
# retriever = FAISS.from_documents(docs, embedding=embedding).as_retriever(search_kwargs={"k": 3})

# # --- QA Chain ---
# llm = Azurellm().azure_client_openai()
# qa_chain = RetrievalQA.from_chain_type(
#     llm=llm,
#     retriever=retriever,
#     chain_type="stuff",
#     return_source_documents=True,
# )
#
# # --- Query + Collect Results ---
# queries = [
#     "How can I query for a monitor's status using GraphQL?",
#     "How do I delete a model?",
#     "How much does an enterprise license of Arize cost?",
#     "How do I log a prediction using the python SDK?",
# ]
#
# qa_pairs = []
# for query in queries:
#     output = qa_chain.invoke({"query": query})
#     answer = output.get("result", output)
#     qa_pairs.append({"question": query, "ground_truth": "", "answer": answer})
#
client = px.Client(endpoint=PHOENIX_BASE, api_key=os.getenv("PHOENIX_API_KEY"))
print("Phoenix UI:", PHOENIX_BASE)
# spans_df = client.get_spans_dataframe(project_name=PROJECT)
# queries_df = get_qa_with_reference(client, project_name=PROJECT)
# retrieved_documents_df = get_retrieved_documents(client, project_name=PROJECT)
#
#
# queries_df.to_csv("queries_df.csv", index=False)
# retrieved_documents_df.to_csv("retrieved_documents_df.csv", index=False)


from dataclasses import dataclass, field
from typing import Any, Dict, Optional
# Phoenix base model
from phoenix.evals.models.openai import OpenAIModel as PhoenixOpenAIModel
# OpenAI SDK
from openai import OpenAI, AzureOpenAI

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from phoenix.evals.models.openai import OpenAIModel as PhoenixOpenAIModel
from openai import OpenAI, AzureOpenAI

queries_df = pd.read_csv("queries_df.csv")
retrieved_documents_df = pd.read_csv("retrieved_documents_df.csv")


from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from phoenix.evals.models.openai import OpenAIModel as PhoenixOpenAIModel
from openai import OpenAI, AzureOpenAI

from phoenix.evals import (
    HALLUCINATION_PROMPT_RAILS_MAP,
    HALLUCINATION_PROMPT_TEMPLATE,
    QA_PROMPT_RAILS_MAP,
    QA_PROMPT_TEMPLATE,
    OpenAIModel,
    llm_classify,
)

@dataclass(eq=False)
class OpenAIModel(PhoenixOpenAIModel):
    http_client: Optional[Any] = field(default=None, repr=False, kw_only=True)
    default_headers: Optional[Dict[str, str]] = field(default=None, repr=False, kw_only=True)
    extra_headers: Optional[Dict[str, str]] = field(default=None, repr=False, kw_only=True)
    max_retries: int = field(default=5, repr=False, kw_only=True)
    timeout: Optional[float] = field(default=30, repr=False, kw_only=True)

    def _make_sdk_client(self):
        common: Dict[str, Any] = {}

        # standard Phoenix fields
        if getattr(self, "api_key", None) is not None:
            common["api_key"] = self.api_key
        if getattr(self, "organization", None) is not None:
            common["organization"] = self.organization
        if getattr(self, "base_url", None) is not None:
            common["base_url"] = self.base_url

        # our extensions
        if self.default_headers is not None:
            common["default_headers"] = self.default_headers
        if self.http_client is not None:
            common["http_client"] = self.http_client
        if self.max_retries is not None:
            common["max_retries"] = self.max_retries
        if self.timeout is not None:
            common["timeout"] = self.timeout

        # choose Azure or public OpenAI
        if getattr(self, "azure_endpoint", None):
            return AzureOpenAI(
                api_version=getattr(self, "api_version", None),
                azure_endpoint=self.azure_endpoint,
                azure_deployment=getattr(self, "azure_deployment", None),
                azure_ad_token=get_bearer_token(),
                azure_ad_token_provider=getattr(self, "azure_ad_token_provider", None),
                **common,
            )
        return OpenAI(**common)

    def reload_client(self) -> None:
        """
        Phoenix calls this to refresh the client; we rebuild using our custom constructor.
        """
        self._client = self._make_sdk_client()

    @property
    def invocation_params(self) -> Dict[str, Any]:
        """
        Extend the base invocation params to include extra_headers per request.
        """
        params = dict(super().invocation_params)  # keep everything Phoenix adds
        if self.extra_headers:
            params["extra_headers"] = self.extra_headers
        return params


import httpx
import json
from pathlib import Path
from utils.bedrock import get_bearer_token

# Define the cert path
token = get_bearer_token()
root_path = Path(__file__).resolve().parent.parent.parent # Adjust based on the file's location
ssl_context = root_path / "utils" / "certs" / "ADP_Internal_Root_CA_GN2.pem"
httpx_client = httpx.Client(verify=str(ssl_context))
llm_client = AzureOpenAI(
    api_version="2023-05-15",
    azure_endpoint="https://aigateway-amrs-nonprod.oneadp.com/v0/r0",
    azure_deployment="gpt-4o-mini_2024-07-18-pgo-amrs",
    api_key=token,
    http_client=httpx_client,
)
response = llm_client.chat.completions.create(
    model='gpt-4.1-mini_2025-04-14-pgo-amrs',
    messages=[
        {"role": "system", "content": "You are a great storyteller."},
        {"role": "user", "content": "Once upon a time in a galaxy far, far away..."}
    ],
)

# print(response.choices[0].message.content)
eval_model = OpenAIModel(
    model ="o4-mini_2025-04-16-pgo-amrs",
    azure_deployment="o4-mini_2025-04-16-pgo-amrs",
    azure_endpoint="https://aigateway-amrs-nonprod.oneadp.com/v0/r0",
    api_version="2025-01-01-preview",
    api_key = token,
    http_client=httpx_client,
    timeout=30,
    model_kwargs = {
        'model': "o4-mini_2025-04-16-pgo-amrs"
    },
    default_headers= {
        "User-Agent": "ADPEval/1.0",
        "x-ms-client-request-id": "ADPEval-12345",
    }
)

hallucination_evaluator = HallucinationEvaluator(eval_model)
qa_correctness_evaluator = QAEvaluator(eval_model)
relevance_evaluator = RelevanceEvaluator(eval_model)

hallucination_eval_df, qa_correctness_eval_df = run_evals(
    dataframe=queries_df,
    evaluators=[hallucination_evaluator, qa_correctness_evaluator],
    provide_explanation=True,
)
print(hallucination_eval_df)

relevance_eval_df = run_evals(
    dataframe=retrieved_documents_df,
    evaluators=[relevance_evaluator],
    provide_explanation=True,
)[0]
print(relevance_eval_df)

# client.log_evaluations(
#     SpanEvaluations(eval_name="Hallucination", dataframe=hallucination_eval_df),
#     SpanEvaluations(eval_name="QA Correctness", dataframe=qa_correctness_eval_df),
#     DocumentEvaluations(eval_name="Relevance", dataframe=relevance_eval_df),
# )
#
# # --- Evaluation ---
# queries_df = pd.DataFrame(qa_pairs)
# print(queries_df)
#
# model = OpenAIModel(model="gpt-4", temperature=0.0, )
# print(model("Hello world, this is a test if you are working?"))
#
# rails = list(HALLUCINATION_PROMPT_RAILS_MAP.values())
# hallucination_classifications = llm_classify(
#     dataframe=queries_df,
#     template=HALLUCINATION_PROMPT_TEMPLATE,
#     model=model,
#     rails=rails,
#     concurrency=20
# )
# print(hallucination_classifications["label"].tolist())
#
# # # Hallucination Eval
# # hallucination_eval = llm_classify(
# #     data=queries_df,
# #     model=OpenAIModel(model="gpt-4o", temperature=0.0),
# #     template=HALLUCINATION_PROMPT_TEMPLATE,
# #     rails=list(HALLUCINATION_PROMPT_RAILS_MAP.values()),
# #     provide_explanation=True,
# # )
# # hallucination_eval["score"] = (hallucination_eval.label == "factual").astype(int)
#
# # # QA Correctness Eval
# # qa_eval = llm_classify(
# #     data=queries_df,
# #     model=OpenAIModel(model="gpt-4o", temperature=0.0),
# #     template=QA_PROMPT_TEMPLATE,
# #     rails=list(QA_PROMPT_RAILS_MAP.values()),
# #     provide_explanation=True,
# #     concurrency=4,
# # )
# # qa_eval["score"] = (qa_eval.label == "correct").astype(int)
# #
# # # --- Summary ---
# # print("\n=== Hallucination Evaluation ===")
# # print(hallucination_eval[["question", "label", "explanation", "score"]])
# #
# # print("\n=== QA Correctness Evaluation ===")
# # print(qa_eval[["question", "label", "explanation", "score"]])
