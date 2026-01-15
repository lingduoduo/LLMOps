#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.custom_vector_database_example.py
"""
import uuid
from typing import List, Optional, Any, Iterable, Type

import dotenv
import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from langchain_openai import OpenAIEmbeddings


class MemoryVectorStore(VectorStore):
    """An in-memory vector database based on Euclidean distance"""
    store: dict = {}  # Temporary variable for storing vectors

    def __init__(self, embedding: Embeddings):
        self._embedding = embedding

    def add_texts(self, texts: Iterable[str], metadatas: Optional[List[dict]] = None, **kwargs: Any) -> List[str]:
        """Add data to the vector store"""
        # 1. Validate metadata format
        if metadatas is not None and len(metadatas) != len(texts):
            raise ValueError("Metadata length mismatch")

        # 2. Convert texts into embeddings and generate IDs
        embeddings = self._embedding.embed_documents(texts)
        ids = [str(uuid.uuid4()) for _ in texts]

        # 3. Store each record
        for idx, text in enumerate(texts):
            self.store[ids[idx]] = {
                "id": ids[idx],
                "text": text,
                "vector": embeddings[idx],
                "metadata": metadatas[idx] if metadatas is not None else {},
            }

        return ids

    def similarity_search(self, query: str, k: int = 4, **kwargs: Any) -> List[Document]:
        """Perform similarity search given a query"""
        # 1. Embed the query
        embedding = self._embedding.embed_query(query)

        # 2. Compute Euclidean distance to all stored vectors
        result = []
        for key, record in self.store.items():
            distance = self._euclidean_distance(embedding, record["vector"])
            result.append({"distance": distance, **record})

        # 3. Sort results by ascending distance
        sorted_result = sorted(result, key=lambda x: x["distance"])

        # 4. Return top-k closest results
        result_k = sorted_result[:k]

        return [
            Document(page_content=item["text"], metadata={**item["metadata"], "score": item["distance"]})
            for item in result_k
        ]

    @classmethod
    def from_texts(cls: Type["MemoryVectorStore"], texts: List[str], embedding: Embeddings,
                   metadatas: Optional[List[dict]] = None,
                   **kwargs: Any) -> "MemoryVectorStore":
        """Construct a vector store from texts and optional metadata"""
        memory_vector_store = cls(embedding=embedding)
        memory_vector_store.add_texts(texts, metadatas, **kwargs)
        return memory_vector_store

    @classmethod
    def _euclidean_distance(cls, vec1: list, vec2: list) -> float:
        """Compute Euclidean distance between two vectors"""
        return np.linalg.norm(np.array(vec1) - np.array(vec2))


dotenv.load_dotenv()

# 1. Prepare initial data and embedding model
texts = [
    "Benben is a cat who loves sleeping.",
    "I enjoy listening to music at night; it helps me relax.",
    "A cat is napping on the windowsill—so adorable.",
    "Learning new skills is a goal everyone should strive for.",
    "My favorite food is pasta, especially with tomato sauce.",
    "I had a strange dream last night where I flew through space.",
    "My phone suddenly shut off, and it made me anxious.",
    "I read every day—it makes me feel fulfilled.",
    "They planned a weekend picnic together, hoping for good weather.",
    "My dog loves chasing balls and looks very happy doing it.",
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
embedding = OpenAIEmbeddings(model="text-embedding-3-small")

# 2. Build custom vector store
db = MemoryVectorStore(embedding=embedding)

ids = db.add_texts(texts, metadatas)
print(ids)

# 3. Perform similarity search
print(db.similarity_search("Who is Benben?"))
