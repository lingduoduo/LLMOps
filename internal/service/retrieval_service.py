#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : retrieval_service.py
"""
from dataclasses import dataclass
from uuid import UUID

from injector import inject
from langchain.retrievers import EnsembleRetriever
from langchain_core.documents import Document as LCDocument
from sqlalchemy import update

from internal.entity.dataset_entity import RetrievalStrategy, RetrievalSource
from internal.exception import NotFoundException
from internal.model import Dataset, DatasetQuery, Segment, Account
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
            account: Account,
            retrieval_strategy: str = RetrievalStrategy.SEMANTIC,
            k: int = 4,
            score: float = 0,
            retrival_source: str = RetrievalSource.HIT_TESTING,
    ) -> list[LCDocument]:
        """
        Execute retrieval over the given datasets using the query, and return documents
        (and scores where applicable).

        If the retrieval strategy is full-text search, scores will be 0.
        """
        # 1. Fetch datasets, validate permissions, and normalize dataset_ids
        datasets = (
            self.db.session.query(Dataset)
            .filter(
                Dataset.id.in_(dataset_ids),
                Dataset.account_id == account.id,
            )
            .all()
        )
        if datasets is None or len(datasets) == 0:
            raise NotFoundException("No datasets available for retrieval")

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
            search_kwargs={
                "k": k,
            },
        )
        hybrid_retriever = EnsembleRetriever(
            retrievers=[semantic_retriever, full_text_retriever],
            weights=[0.5, 0.5],
        )

        # 3. Execute retrieval based on the strategy
        if retrieval_strategy == RetrievalStrategy.SEMANTIC:
            lc_documents = semantic_retriever.invoke(query)[:k]
        elif retrieval_strategy == RetrievalStrategy.FULL_TEXT:
            lc_documents = full_text_retriever.invoke(query)[:k]
        else:
            lc_documents = hybrid_retriever.invoke(query)[:k]

        # 4. Add dataset query logs (store only unique records:
        #    even if a dataset returns multiple documents, record only once)
        unique_dataset_ids = list(
            set(str(lc_document.metadata["dataset_id"]) for lc_document in lc_documents)
        )
        for dataset_id in unique_dataset_ids:
            self.create(
                DatasetQuery,
                dataset_id=dataset_id,
                query=query,
                source=retrival_source,
                # TODO: adjust after the APP configuration module is finished
                source_app_id=None,
                created_by=account.id,
            )

        # 5. Batch-update segment hit counts (build and execute the statement)
        with self.db.auto_commit():
            stmt = (
                update(Segment)
                .where(
                    Segment.id.in_(
                        [
                            lc_document.metadata["segment_id"]
                            for lc_document in lc_documents
                        ]
                    )
                )
                .values(hit_count=Segment.hit_count + 1)
            )
            self.db.session.execute(stmt)

        return lc_documents
