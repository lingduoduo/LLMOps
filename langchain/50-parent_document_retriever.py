#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.parent_document_retriever_example.py
"""
import os

import dotenv
import weaviate
from langchain.retrievers import ParentDocumentRetriever
from langchain.storage import LocalFileStore
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_weaviate import WeaviateVectorStore
from weaviate.auth import AuthApiKey

# Load environment variables
dotenv.load_dotenv()

# 1. Create file loaders and load all documents
loaders = [
    UnstructuredFileLoader("./ecommerce_product_data.txt"),
    UnstructuredFileLoader("./project_api_docs.md"),
]
documents = []
for loader in loaders:
    documents.extend(loader.load())

# 2. Initialize a text splitter for chunking child documents
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
)

# 3. Set up the vector store and local byte store
vector_store = WeaviateVectorStore(
    client=weaviate.connect_to_wcs(
        cluster_url=os.environ.get("WC_CLUSTER_URL"),
        auth_credentials=AuthApiKey(os.environ["WCD_API_KEY"]),
    ),
    index_name="ParentDocument",
    text_key="text",
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)
byte_store = LocalFileStore("./parent-document")

# 4. Create the ParentDocumentRetriever
retriever = ParentDocumentRetriever(
    vectorstore=vector_store,
    byte_store=byte_store,
    child_splitter=text_splitter,
)

# 5. (Optional) Add the loaded documents to the retriever
retriever.add_documents(documents, ids=None)

# 6. Perform a similarity search
search_results = retriever.vectorstore.similarity_search(
    "Share some configuration examples for LLMOps applications"
)
print(search_results)
print(f"Number of results: {len(search_results)}")

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : 1.parent_document_retriever_example.py
"""
import dotenv
import weaviate
from langchain.retrievers import ParentDocumentRetriever
from langchain.storage import LocalFileStore
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_weaviate import WeaviateVectorStore
from weaviate.auth import AuthApiKey

# Load environment variables
dotenv.load_dotenv()

# 1. Create file loaders and load all documents
loaders = [
    UnstructuredFileLoader("./ecommerce_product_data.txt"),
    UnstructuredFileLoader("./project_api_docs.md"),
]
documents = []
for loader in loaders:
    documents.extend(loader.load())

# 2. Initialize parent and child text splitters
parent_splitter = RecursiveCharacterTextSplitter(chunk_size=2000)
child_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

# 3. Set up the vector store and local byte store
vector_store = WeaviateVectorStore(
    client=weaviate.connect_to_wcs(
        cluster_url=os.environ.get("WC_CLUSTER_URL"),
        auth_credentials=AuthApiKey(os.environ["WCD_API_KEY"]),
    ),
    index_name="ParentDocument",
    text_key="text",
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)
byte_store = LocalFileStore("./parent-document")

# 4. Create the ParentDocumentRetriever with both splitters
retriever = ParentDocumentRetriever(
    vectorstore=vector_store,
    byte_store=byte_store,
    parent_splitter=parent_splitter,
    child_splitter=child_splitter,
)

# 5. Add the documents to the retriever (auto-generates IDs if None)
retriever.add_documents(documents, ids=None)

# 6. Perform a retrieval query and print results
search_results = retriever.invoke("Share some configuration examples for LLMOps applications")
print(search_results)
print(f"Number of results: {len(search_results)}")
