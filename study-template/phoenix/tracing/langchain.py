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
    "Where do I get my insurance ID cards?",
    "How do I use my Health Savings Account (HSA)?",
    "How do I use my Flexible Spending Account (FSA)?",
    "What medical plans are available?",
    "What vision plans are available?",
    "What dental plans are available?",
    "Is my job protected while I'm out on leave?",
    "Can I take time off during probationary periods?",
    "Will my benefits continue during an unpaid leave?",
    "Who is eligible to be added to my benefit plans as a dependent?",
]
docs = [Document(page_content=txt) for txt in sample_docs]
docs = RecursiveCharacterTextSplitter(chunk_size=30, chunk_overlap=5).split_documents(docs)

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
    "my insurance ID cards",
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

