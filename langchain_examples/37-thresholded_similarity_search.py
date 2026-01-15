#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : thresholded_similarity_search_example.py
"""
import os

# Allow duplicate OpenMP runtime loading on macOS as a workaround
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

# Load environment variables
dotenv.load_dotenv()

# Initialize the embedding model
embedding = OpenAIEmbeddings(model="text-embedding-3-small")

# Prepare a set of sample documents
documents = [
    Document(page_content="Benny is a cat who loves sleeping", metadata={"page": 1}),
    Document(page_content="I enjoy listening to music at night; it helps me relax.", metadata={"page": 2}),
    Document(page_content="The cat is dozing on the windowsill; it looks very cute.", metadata={"page": 3}),
    Document(page_content="Learning a new skill is a goal everyone should pursue.", metadata={"page": 4}),
    Document(page_content="My favorite food is pasta, especially with tomato sauce.", metadata={"page": 5}),
    Document(page_content="Last night I had a strange dream, dreaming I was flying in space.", metadata={"page": 6}),
    Document(page_content="My phone suddenly shut down; it made me anxious.", metadata={"page": 7}),
    Document(page_content="Reading is something I do every day; it makes me feel fulfilled.", metadata={"page": 8}),
    Document(page_content="They planned a weekend picnic together; they hope the weather will be good.",
             metadata={"page": 9}),
    Document(page_content="My dog loves chasing balls; it looks very happy.", metadata={"page": 10}),
]

# Build the FAISS index from documents
db = FAISS.from_documents(documents, embedding)

# Perform a similarity search with a relevance score threshold
results = db.similarity_search_with_relevance_scores(
    "I have a cat named Benny",
    score_threshold=0.2
)

# Print out documents and their relevance scores
print(results)

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : max_marginal_relevance_example.py
"""
import os

import dotenv
import weaviate
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_weaviate import WeaviateVectorStore
from weaviate.auth import AuthApiKey

# 0. Allow duplicate OpenMP runtime on macOS (if needed)
# os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Load environment variables
dotenv.load_dotenv()

# 1. Initialize loader and recursive character splitter
loader = UnstructuredMarkdownLoader("./project_api_docs.md")
text_splitter = RecursiveCharacterTextSplitter(
    separators=[
        "\n\n",  # double newline
        "\n",  # single newline
        "。|！|？",  # Chinese punctuation: period, exclamation, question
        "\.\s|!\s|\?\s",  # English punctuation followed by space
        "；|;\s",  # Chinese/English semicolon
        "，|,\s",  # Chinese/English comma
        " ",  # space
        ""  # fallback
    ],
    is_separator_regex=True,
    chunk_size=500,
    chunk_overlap=50,
    add_start_index=True,
)

# 2. Load and split the documents
documents = loader.load()
chunks = text_splitter.split_documents(documents)

# 3. Store chunks in a Weaviate vector database
db = WeaviateVectorStore(
    client=weaviate.connect_to_wcs(
        cluster_url=os.environ.get("WC_CLUSTER_URL"),
        auth_credentials=AuthApiKey(os.environ["WCD_API_KEY"]),
    ),
    index_name="DatasetDemo",
    text_key="text",
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)
db.add_documents(chunks)

# 4. Convert to a retriever with similarity score threshold
retriever = db.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"k": 10, "score_threshold": 0.5},
)

# 5. Query the retriever
query = "Information about API configuration"
results = retriever.invoke(query)

# 6. Output results
for doc in results:
    print(doc.page_content[:100])  # print first 100 characters of each result
print(f"Total results: {len(results)}")

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : max_marginal_relevance_search_example.py
"""
import os

import dotenv
import weaviate
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_weaviate import WeaviateVectorStore
from weaviate.auth import AuthApiKey

# Load environment variables
dotenv.load_dotenv()

# 1. Initialize the markdown loader and recursive character splitter
loader = UnstructuredMarkdownLoader("./project_api_docs.md")
text_splitter = RecursiveCharacterTextSplitter(
    separators=[
        "\n\n",  # Double newline
        "\n",  # Single newline
        "。|！|？",  # Chinese punctuation: period, exclamation, question
        "\.\s|!\s|\?\s",  # English punctuation followed by space
        "；|;\s",  # Chinese/English semicolon
        "，|,\s",  # Chinese/English comma
        " ",  # Space
        ""  # Fallback separator
    ],
    is_separator_regex=True,
    chunk_size=500,
    chunk_overlap=50,
    add_start_index=True,
)

# 2. Load and split the documents
docs = loader.load()
chunks = text_splitter.split_documents(docs)

# 3. Store chunks in a Weaviate vector database
db = WeaviateVectorStore(
    client=weaviate.connect_to_wcs(
        cluster_url=os.environ.get("WC_CLUSTER_URL"),
        auth_credentials=AuthApiKey(os.environ["WCD_API_KEY"]),
    ),
    index_name="DatasetDemo",
    text_key="text",
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)
# db.add_documents(chunks)

# 4. Perform Max Marginal Relevance search
query = "What API configuration options are available for the application?"
results = db.max_marginal_relevance_search(query)

# 5. Output the search results (first 100 characters each)
for doc in results:
    print(doc.page_content[:100])
    print("-----------")
