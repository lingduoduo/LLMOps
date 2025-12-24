#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : custom_retriever_example.py
"""
from typing import List

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever


class CustomRetriever(BaseRetriever):
    """A custom retriever that returns documents containing the query string."""
    documents: List[Document]
    k: int

    def _get_relevant_documents(
            self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """
        Return up to `k` documents whose content includes the query (case-insensitive).
        """
        matching_documents: List[Document] = []
        for doc in self.documents:
            if len(matching_documents) >= self.k:
                break
            if query.lower() in doc.page_content.lower():
                matching_documents.append(doc)
        return matching_documents


# 1. Define sample documents
documents = [
    Document(page_content="Benny is a cat who loves sleeping", metadata={"page": 1}),
    Document(page_content="I enjoy listening to music at night; it helps me relax.", metadata={"page": 2}),
    Document(page_content="The cat is dozing on the windowsill; it looks very cute.", metadata={"page": 3}),
    Document(page_content="Learning a new skill is a goal everyone should pursue.", metadata={"page": 4}),
    Document(page_content="My favorite food is pasta, especially with tomato sauce.", metadata={"page": 5}),
    Document(page_content="Last night I had a strange dream about flying in space.", metadata={"page": 6}),
    Document(page_content="My phone suddenly shut down, which made me anxious.", metadata={"page": 7}),
    Document(page_content="Reading is something I do every day; I find it very fulfilling.", metadata={"page": 8}),
    Document(page_content="They planned a weekend picnic together, hoping for good weather.", metadata={"page": 9}),
    Document(page_content="My dog loves chasing balls; it looks very happy.", metadata={"page": 10}),
]

# 2. Create the retriever with k=3
retriever = CustomRetriever(documents=documents, k=3)

# 3. Invoke the retriever with a query and print results
results = retriever.invoke("cat")
print("Retrieved documents:", results)
print("Number of results:", len(results))
