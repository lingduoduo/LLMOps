#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : vector_database_service.py
"""
from dataclasses import dataclass
from typing import Any

from flask import Flask
from flask_weaviate import FlaskWeaviate
from injector import inject
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_weaviate import WeaviateVectorStore
from weaviate.collections import Collection

from .embeddings_service import EmbeddingsService

COLLECTION_NAME = "Dataset"


@inject
@dataclass
class VectorDatabaseService:
    """Vector database service"""
    weaviate: FlaskWeaviate
    embeddings_service: EmbeddingsService

    # def __init__(self):
    #     """Constructor that initializes the vector database client and LangChain vector store instance"""
    #     # 1. Connect to the Weaviate vector database
    #     skip_checks = os.getenv("WEAVIATE_SKIP_INIT_CHECKS", "false").lower() == "true"
    #     # self.client = weaviate.connect_to_weaviate_cloud(
    #     #     cluster_url=weaviate_url,
    #     #     auth_credentials=Auth.api_key(weaviate_api_key),
    #     #     additional_config=AdditionalConfig(timeout=Timeout(init=60)),
    #     #     skip_init_checks=skip_checks,
    #     # )
    #     self.client = weaviate.connect_to_local(
    #         host=os.getenv("WEAVIATE_HOST"),
    #         port=os.getenv("WEAVIATE_PORT"),
    #     )
    #     print(self.client.is_ready())
    #
    #     # 2. Create the LangChain vector store
    #     self.vector_store = WeaviateVectorStore(
    #         client=self.client,
    #         index_name="Dataset",
    #         text_key="text",
    #         embedding=OpenAIEmbeddings(model="text-embedding-3-small")
    #     )
    @property
    def vector_store(self) -> WeaviateVectorStore:
        return WeaviateVectorStore(
            client=self.weaviate.client,
            index_name=COLLECTION_NAME,
            text_key="text",
            embedding=self.embeddings_service.cache_backed_embeddings,
        )

    async def _get_client(self, flask_app: Flask):
        with flask_app.app_context():
            return self.weaviate.client

    async def add_documents(self, documents: list[Document], **kwargs: Any):
        """Add documents to the vector database."""
        self.vector_store.add_documents(documents, **kwargs)

    def get_retriever(self) -> VectorStoreRetriever:
        """Get the retriever"""
        return self.vector_store.as_retriever()

    @classmethod
    def combine_documents(cls, documents: list[Document]) -> str:
        """Combine a list of documents using newline characters"""
        return "\n\n".join([document.page_content for document in documents])

    @property
    def collection(self) -> Collection:
        return self.weaviate.client.collections.get(COLLECTION_NAME)

#     def add_dataset_documents(
#             self,
#             dataset_id: str,
#             texts: list[str],
#     ) -> None:
#         """
#         Store raw texts in Weaviate under the given dataset_id.
#         """
#         docs = [
#             Document(
#                 page_content=text,
#                 metadata={"dataset_id": dataset_id,
#                           "document_enabled": True,
#                           "segment_enabled": True
#                           },
#             )
#             for text in texts
#         ]
#         self.vector_store.add_documents(docs)
#
#
# vdb = VectorDatabaseService()
# vdb.add_dataset_documents(
#     dataset_id="1cbb6449-5463-49a4-b0ef-1b94cdf747d7",
#     texts=[
#         "Intro to front-end prompts and patterns. Best practices for writing prompts for React components...",
#     ],
# )
# vdb.add_dataset_documents(
#     dataset_id="798f5324-c82e-44c2-94aa-035afbe88839",
#     texts=[
#         "DevOps runbook for LLM observability dashboards.",
#     ],
# )
