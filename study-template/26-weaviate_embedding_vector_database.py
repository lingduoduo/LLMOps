#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.weaviate_embedding_vector_database_example.py
"""
import os

import dotenv
import weaviate
from langchain_openai import OpenAIEmbeddings
from langchain_weaviate import WeaviateVectorStore
from weaviate.classes.init import Auth
from weaviate.classes.query import Filter

dotenv.load_dotenv()

# 1. Raw text data and metadata
texts = [
    "Benben is a cat who loves to sleep.",
    "I like listening to music at night; it makes me feel relaxed.",
    "The cat is napping on the windowsill and looks very cute.",
    "Learning new skills is a goal everyone should pursue.",
    "My favorite food is pasta, especially the kind with tomato sauce.",
    "Last night I had a strange dream—dreamt I was flying in space.",
    "My phone suddenly shut down, which made me a bit anxious.",
    "Reading is something I do every day—it makes me feel fulfilled.",
    "They planned a weekend picnic together, hoping for good weather.",
    "My dog loves to chase balls and looks super happy doing it.",
]
metadatas = [
    {"page": 1},
    {"page": 2},
    {"page": 3},
    {"page": 4},
    {"page": 5},
    {"page": 6, "account_id": 1},
    {"page": 7},
    {"page": 8},
    {"page": 9},
    {"page": 10},
]

# 2. Create client connection
# client = weaviate.connect_to_local("192.168.2.120", "8080")
# Alternatively, connect to Weaviate Cloud Service (WCS)
# Best practice: store your credentials in environment variables
weaviate_url = os.environ["WCD_CLUSTER_URL"]
weaviate_api_key = os.environ["WCD_API_KEY"]

# Connect to Weaviate Cloud
client = weaviate.connect_to_weaviate_cloud(
    cluster_url=weaviate_url,
    auth_credentials=Auth.api_key(weaviate_api_key),
)
print(client.is_ready())

embedding = OpenAIEmbeddings(model="text-embedding-3-small")

# 3. Create LangChain vector store instance
db = WeaviateVectorStore(
    client=client,
    index_name="Dataset",
    text_key="text",
    embedding=embedding,
)

# 4. Add data
ids = db.add_texts(texts, metadatas)
print(ids)

# 5. Perform similarity search with a filter
filters = Filter.by_property("page").greater_or_equal(5)
print(db.similarity_search_with_score("Benben", filters=filters))

# Create a retriever and invoke a query
retriever = db.as_retriever()
print(retriever.invoke("Benben"))
