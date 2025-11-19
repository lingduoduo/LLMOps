#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : retrieval_service.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import Flask
from injector import inject
from langchain.retrievers import EnsembleRetriever
from langchain_core.documents import Document as LCDocument
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool, tool
from sqlalchemy import update

from internal.core.agent.entities.agent_entity import DATASET_RETRIEVAL_TOOL_NAME
from internal.entity.dataset_entity import RetrievalStrategy, RetrievalSource
from internal.exception import NotFoundException
from internal.lib.helper import combine_documents
from internal.model import Dataset, DatasetQuery, Segment
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .jieba_service import JiebaService
from .vector_database_service import VectorDatabaseService


@inject
@dataclass
class RetrievalService(BaseService):
    """Retrieval service"""
    db: SQLAlchemy
    jieba_service: JiebaService
    vector_database_service: VectorDatabaseService

    def search_in_datasets(
            self,
            dataset_ids: list[UUID],
            query: str,
            account_id: UUID,
            retrieval_strategy: str = RetrievalStrategy.SEMANTIC,
            k: int = 4,
            score: float = 0,
            retrival_source: str = RetrievalSource.HIT_TESTING,
    ) -> list[LCDocument]:
        """
        Execute retrieval using the given query + dataset list, and return
        retrieved documents with scores.
        (If using full-text retrieval, score = 0)
        """
        # 1. Fetch datasets, validate permissions, and refresh dataset IDs
        datasets = (
            self.db.session.query(Dataset)
            .filter(Dataset.id.in_(dataset_ids), Dataset.account_id == account_id)
            .all()
        )
        if datasets is None or len(datasets) == 0:
            raise NotFoundException("No dataset is available for retrieval.")

        dataset_ids = [dataset.id for dataset in datasets]

        # 2. Build different types of retrievers
        from internal.core.retrievers import SemanticRetriever, FullTextRetriever

        semantic_retriever = SemanticRetriever(
            dataset_ids=dataset_ids,
            vector_store=self.vector_database_service.vector_store,
            search_kwargs={
                "k": k,
                "score_threshold": score,
            },
        )

        full_text_retriever = FullTextRetriever(
            db=self.db,
            dataset_ids=dataset_ids,
            jieba_service=self.jieba_service,
            search_kwargs={"k": k},
        )

        hybrid_retriever = EnsembleRetriever(
            retrievers=[semantic_retriever, full_text_retriever],
            weights=[0.5, 0.5],
        )

        # 3. Execute retrieval based on selected strategy
        if retrieval_strategy == RetrievalStrategy.SEMANTIC:
            lc_documents = semantic_retriever.invoke(query)[:k]
        elif retrieval_strategy == RetrievalStrategy.FULL_TEXT:
            lc_documents = full_text_retriever.invoke(query)[:k]
        else:
            lc_documents = hybrid_retriever.invoke(query)[:k]

        # 4. Create dataset query records (store only unique hits per dataset)
        unique_dataset_ids = list(
            set(str(doc.metadata["dataset_id"]) for doc in lc_documents)
        )
        for dataset_id in unique_dataset_ids:
            self.create(
                DatasetQuery,
                dataset_id=dataset_id,
                query=query,
                source=retrival_source,
                # TODO: adjust after the APP config module is completed
                source_app_id=None,
                created_by=account_id,
            )

        # 5. Batch update segment hit_count for all retrieved segments
        with self.db.auto_commit():
            stmt = (
                update(Segment)
                .where(
                    Segment.id.in_(
                        [doc.metadata["segment_id"] for doc in lc_documents]
                    )
                )
                .values(hit_count=Segment.hit_count + 1)
            )
            self.db.session.execute(stmt)

        return lc_documents

    def create_langchain_tool_from_search(
            self,
            flask_app: Flask,
            dataset_ids: list[UUID],
            account_id: UUID,
            retrieval_strategy: str = RetrievalStrategy.SEMANTIC,
            k: int = 4,
            score: float = 0,
            retrival_source: str = RetrievalSource.HIT_TESTING,
    ) -> BaseTool:
        """Construct a LangChain dataset-retrieval tool based on the given parameters."""

        class DatasetRetrievalInput(BaseModel):
            """Input schema for dataset retrieval tool"""
            query: str = Field(description="Query string for dataset search")

        @tool(DATASET_RETRIEVAL_TOOL_NAME, args_schema=DatasetRetrievalInput)
        def dataset_retrieval(query: str) -> str:
            """
            If you need to search extended dataset content—especially when
            user questions exceed your knowledge—you may call this tool.
            Input: search query string
            Output: concatenated retrieved text content as a string.
            """
            # 1. Execute retrieval through search_in_datasets
            with flask_app.app_context():
                documents = self.search_in_datasets(
                    dataset_ids=dataset_ids,
                    query=query,
                    account_id=account_id,
                    retrieval_strategy=retrieval_strategy,
                    k=k,
                    score=score,
                    retrival_source=retrival_source,
                )

            # 2. Convert retrieved documents to a string
            if len(documents) == 0:
                return "No related content found in the dataset."

            return combine_documents(documents)

        return dataset_retrieval
