#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : faiss_service.py
"""
import os

from injector import inject
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool, tool

from internal.core.agent.entities.agent_entity import DATASET_RETRIEVAL_TOOL_NAME
from internal.lib.helper import combine_documents
from .embeddings_service import EmbeddingsService


@inject
class FaissService:
    """Faiss Vector Database Service"""
    faiss: FAISS
    embeddings_service: EmbeddingsService

    def __init__(self, embeddings_service: EmbeddingsService):
        """Constructor: initializes the Faiss vector database"""
        # 1. Assign embeddings_service
        self.embeddings_service = embeddings_service

        # 2. Get the internal path and compute the actual local path of the vector database
        internal_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        faiss_vector_store_path = os.path.join(internal_path, "core", "vector_store")

        # 3. Initialize the Faiss vector database
        self.faiss = FAISS.load_local(
            folder_path=faiss_vector_store_path,
            embeddings=self.embeddings_service.embeddings,
            allow_dangerous_deserialization=True,
        )

    def convert_faiss_to_tool(self) -> BaseTool:
        """Convert the Faiss vector database retriever into a LangChain tool"""
        # 1. Convert Faiss database into a retriever
        retrieval = self.faiss.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 20},
        )

        # 2. Build a retrieval chain and merge retrieved documents into a string
        search_chain = retrieval | combine_documents

        class DatasetRetrievalInput(BaseModel):
            """Input schema for the knowledge base retrieval tool"""
            query: str = Field(description="Query string for knowledge base retrieval")

        @tool(DATASET_RETRIEVAL_TOOL_NAME, args_schema=DatasetRetrievalInput)
        def dataset_retrieval(query: str) -> str:
            """Use this tool to retrieve extended knowledge base content.
            When a user question exceeds your knowledge scope,
            you may call this tool with a query string and return the retrieved content."""
            return search_chain.invoke(query)

        return dataset_retrieval


class FaissIndexBuilder:
    """
    Helper class to build a FAISS vector store from a markdown file.
    This does NOT modify FaissService; it just prepares the vector store
    on disk so that FaissService can load it as before.
    """

    def __init__(self, embeddings_service: EmbeddingsService):
        self.embeddings_service = embeddings_service

    def build_from_markdown(
            self,
            markdown_path: str,
            vector_store_path: str | None = None,
            overwrite: bool = True,
            chunk_size: int = 1000,
            chunk_overlap: int = 200,
    ) -> None:
        """
        Build (or update) a FAISS index from a markdown file.

        - markdown_path:
            * If absolute: used as-is
            * If relative: resolved under <internal>/storage/
        - vector_store_path:
            * If None: defaults to <internal>/core/vector_store
        """
        # Base <internal> path (one level above this file's directory)
        internal_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Resolve vector store path (default: <internal>/core/vector_store)
        if vector_store_path is None:
            vector_store_path = os.path.join(internal_path, "core", "vector_store")
        os.makedirs(vector_store_path, exist_ok=True)

        # Resolve markdown path
        if not os.path.isabs(markdown_path):
            # Treat relative paths as files under <internal>/storage/
            markdown_path = os.path.join(os.path.dirname(internal_path), "storage", "vector_store", markdown_path)

        if not os.path.exists(markdown_path):
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

        # 1. Load markdown file as Documents
        loader = TextLoader(markdown_path, encoding="utf-8")
        raw_documents = loader.load()  # typically a list with one Document

        # 2. Split into smaller chunks for better retrieval
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        documents = splitter.split_documents(raw_documents)

        # 3. Create or update FAISS index
        if overwrite:
            # Create a brand-new index
            faiss = FAISS.from_documents(
                documents,
                self.embeddings_service.embeddings,  # uses OpenAIEmbeddings from EmbeddingsService
            )
        else:
            # Append to existing index if it exists, otherwise create new
            if os.path.exists(vector_store_path) and os.listdir(vector_store_path):
                faiss = FAISS.load_local(
                    folder_path=vector_store_path,
                    embeddings=self.embeddings_service.embeddings,
                    allow_dangerous_deserialization=True,
                )
                faiss.add_documents(documents)
            else:
                faiss = FAISS.from_documents(
                    documents,
                    self.embeddings_service.embeddings,
                )

        # 4. Persist FAISS index to disk
        faiss.save_local(vector_store_path)

# Optional standalone entrypoint: build the vector store & test loading
# if __name__ == "__main__":
#     from redis import Redis
#     from .embeddings_service import EmbeddingsService
#
#     # 1. Initialize Redis client (adjust host/port/db if needed)
#     redis_client = Redis(host="localhost", port=6379, db=0)
#
#     # 2. Initialize EmbeddingsService (OpenAIEmbeddings + Redis cache)
#     embeddings_service = EmbeddingsService(redis_client)
#
#     # 3. Build FAISS index from markdown located at <internal>/storage/executive-summary-2020.md
#     builder = FaissIndexBuilder(embeddings_service)
#     builder.build_from_markdown("executive-summary-2020.md", overwrite=True)
#
#     # 4. Load FAISS via FaissService and get the LangChain tool
#     faiss_service = FaissService(embeddings_service)
#     dataset_tool = faiss_service.convert_faiss_to_tool()
#
#     print("FAISS vector store built and tool is ready to use.")
