#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 01.cache_backed_embedding_example.py
"""
import dotenv
import numpy as np
from langchain.embeddings import CacheBackedEmbeddings
from langchain.storage import LocalFileStore
from langchain_openai import OpenAIEmbeddings
from numpy.linalg import norm

dotenv.load_dotenv()


def cosine_similarity(vector1: list, vector2: list) -> float:
    """Compute cosine similarity between two vectors"""
    # 1. Compute dot product
    dot_product = np.dot(vector1, vector2)

    # 2. Compute vector norms
    norm_vec1 = norm(vector1)
    norm_vec2 = norm(vector2)

    # 3. Compute cosine similarity
    return dot_product / (norm_vec1 * norm_vec2)


# Create base embedding model
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# Wrap with caching layer (cache stored in ./cache/ directory)
embeddings_with_cache = CacheBackedEmbeddings.from_bytes_store(
    embeddings,
    LocalFileStore("./cache/"),
    namespace=embeddings.model,
    query_embedding_cache=True,
)

# Embed a query
query_vector = embeddings_with_cache.embed_query("Hello, I'm Ling, and I live in New York.")

# Embed a list of documents
documents_vector = embeddings_with_cache.embed_documents([
    "Hello, I'm Ling, and I like playing basketball.",
    "The person who live in New York is named Ling.",
    "Stay hungry, stay foolish."
])

print(query_vector)
print(len(query_vector))

print("============")

print(len(documents_vector))
print("Cosine similarity between vector 1 and vector 2:", cosine_similarity(documents_vector[0], documents_vector[1]))
print("Cosine similarity between vector 1 and vector 3:", cosine_similarity(documents_vector[0], documents_vector[2]))
