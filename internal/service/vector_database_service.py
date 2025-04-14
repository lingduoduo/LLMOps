#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : vector_database_service.py
"""
import os

import weaviate
from injector import inject
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_weaviate import WeaviateVectorStore
from weaviate import WeaviateClient
from weaviate.auth import AuthApiKey


@inject
class VectorDatabaseService:
    """Vector database service"""
    client: WeaviateClient
    vector_store: WeaviateVectorStore

    def __init__(self):
        """Constructor that initializes the vector database client and LangChain vector store instance"""
        # 1. Connect to the Weaviate vector database
        self.client = weaviate.connect_to_wcs(
            cluster_url=os.environ.get("WC_CLUSTER_URL"),
            auth_credentials=AuthApiKey(os.environ["WCD_API_KEY"]),
        )

        # 2. Create the LangChain vector store
        self.vector_store = WeaviateVectorStore(
            client=self.client,
            index_name="Dataset",
            text_key="text",
            embedding=OpenAIEmbeddings(model="text-embedding-3-small")
        )

    def get_retriever(self) -> VectorStoreRetriever:
        """Get the retriever"""
        return self.vector_store.as_retriever()

    @classmethod
    def combine_documents(cls, documents: list[Document]) -> str:
        """Combine a list of documents using newline characters"""
        return "\n\n".join([document.page_content for document in documents])
