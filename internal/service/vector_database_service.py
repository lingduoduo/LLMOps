#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : vector_database_service.py
"""
import os

import dotenv
import weaviate
from injector import inject
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_weaviate import WeaviateVectorStore
from weaviate import WeaviateClient
from weaviate.collections import Collection

dotenv.load_dotenv()
import langchain as _lc  # type: ignore

if not hasattr(_lc, "debug"):
    _lc.debug = False

COLLECTION_NAME = "Dataset"


@inject
class VectorDatabaseService:
    """Vector database service"""
    client: WeaviateClient
    vector_store: WeaviateVectorStore

    def __init__(self):
        """Constructor that initializes the vector database client and LangChain vector store instance"""
        # 1. Connect to the Weaviate vector database
        skip_checks = os.getenv("WEAVIATE_SKIP_INIT_CHECKS", "false").lower() == "true"
        # self.client = weaviate.connect_to_weaviate_cloud(
        #     cluster_url=weaviate_url,
        #     auth_credentials=Auth.api_key(weaviate_api_key),
        #     additional_config=AdditionalConfig(timeout=Timeout(init=60)),
        #     skip_init_checks=skip_checks,
        # )
        self.client = weaviate.connect_to_local(
            host=os.getenv("WEAVIATE_HOST"),
            port=os.getenv("WEAVIATE_PORT"),
        )
        print(self.client.is_ready())

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

    @property
    def collection(self) -> Collection:
        return self.client.collections.get(COLLECTION_NAME)
