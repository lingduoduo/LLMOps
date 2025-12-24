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
from weaviate.classes.query import Filter

dotenv.load_dotenv()

import langchain as _lc  # type: ignore

if not hasattr(_lc, "debug"):
    _lc.debug = False

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
# Alternatively, connect to Weaviate Cloud Service (WCS)
client = weaviate.connect_to_local(
    host=os.getenv("WEAVIATE_HOST"),
    port=os.getenv("WEAVIATE_PORT"),
)
print(client.is_ready())

try:
    embedding = OpenAIEmbeddings(model="text-embedding-3-small")
    # 3. Create LangChain vector store instance
    db = (WeaviateVectorStore(
        client=client,
        index_name="Dataset",
        text_key="text",
        embedding=embedding,
    ))

    # 4. Add data
    ids = db.add_texts(texts, metadatas)
    print(ids)

    # 5. Similarity search with a filter
    filters = Filter.by_property("page").greater_or_equal(5)
    print("Search+score (page>=5):")
    for doc, score in db.similarity_search_with_score("Benben", k=3, filters=filters):
        print(f"- score={score:.4f} | text={doc.page_content!r} | meta={doc.metadata}")

    # Create a retriever and invoke a query
    retriever = db.as_retriever(search_kwargs={"k": 3})
    print("Retriever.invoke('Benben'):")
    for d in retriever.invoke("Benben"):
        print(f"- {d.page_content!r} | meta={d.metadata}")

finally:
    # ensure connection is closed to avoid ResourceWarning
    client.close()
