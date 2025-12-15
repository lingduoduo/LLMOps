#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : dataset_service.py
"""
import logging
from dataclasses import dataclass
from uuid import UUID

from injector import inject
from sqlalchemy import desc

from internal.entity.dataset_entity import DEFAULT_DATASET_DESCRIPTION_FORMATTER
from internal.exception import ValidateErrorException, NotFoundException, FailException
from internal.lib.helper import datetime_to_timestamp
from internal.model import Dataset, Segment, DatasetQuery, AppDatasetJoin, Account
from internal.schema.dataset_schema import (
    CreateDatasetReq,
    UpdateDatasetReq,
    GetDatasetsWithPageReq,
    HitReq,
)
from internal.task.dataset_task import delete_dataset
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .retrieval_service import RetrievalService


@inject
@dataclass
class DatasetService(BaseService):
    """Knowledge base service"""
    db: SQLAlchemy
    retrieval_service: RetrievalService

    def create_dataset(self, req: CreateDatasetReq, account: Account) -> Dataset:
        """Create a knowledge base using the provided request data."""
        # 1. Check whether a dataset with the same name already exists under this account
        dataset = self.db.session.query(Dataset).filter_by(
            account_id=account.id,
            name=req.name.data,
        ).one_or_none()
        if dataset:
            raise ValidateErrorException(f"The dataset '{req.name.data}' already exists.")

        # 2. Populate default description if none is provided
        if req.description.data is None or req.description.data.strip() == "":
            req.description.data = DEFAULT_DATASET_DESCRIPTION_FORMATTER.format(
                name=req.name.data
            )

        # 3. Create and return the dataset record
        return self.create(
            Dataset,
            account_id=account.id,
            name=req.name.data,
            icon=req.icon.data,
            description=req.description.data,
        )

    def get_dataset_queries(self, dataset_id: UUID, account: Account) -> list[DatasetQuery]:
        """Retrieve the most recent 10 query records for a dataset."""
        # 1. Retrieve dataset and validate ownership
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise NotFoundException("The dataset does not exist.")

        # 2. Query the latest 10 dataset queries
        dataset_queries = (
            self.db.session.query(DatasetQuery)
            .filter(DatasetQuery.dataset_id == dataset_id)
            .order_by(desc("created_at"))
            .limit(10)
            .all()
        )

        return dataset_queries

    def get_dataset(self, dataset_id: UUID, account: Account) -> Dataset:
        """Retrieve a dataset by ID."""
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise NotFoundException("The dataset does not exist.")

        return dataset

    def update_dataset(self, dataset_id: UUID, req: UpdateDatasetReq, account: Account) -> Dataset:
        """Update dataset information."""
        # 1. Retrieve dataset and validate ownership
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise NotFoundException("The dataset does not exist.")

        # 2. Check for name conflicts after update
        check_dataset = self.db.session.query(Dataset).filter(
            Dataset.account_id == account.id,
            Dataset.name == req.name.data,
            Dataset.id != dataset_id,
        ).one_or_none()
        if check_dataset:
            raise ValidateErrorException(
                f"The dataset name '{req.name.data}' already exists. Please choose another name."
            )

        # 3. Ensure description is not empty
        if req.description.data is None or req.description.data.strip() == "":
            req.description.data = DEFAULT_DATASET_DESCRIPTION_FORMATTER.format(
                name=req.name.data
            )

        # 4. Update dataset fields
        self.update(
            dataset,
            name=req.name.data,
            icon=req.icon.data,
            description=req.description.data,
        )

        return dataset

    def get_datasets_with_page(
            self,
            req: GetDatasetsWithPageReq,
            account: Account
    ) -> tuple[list[Dataset], Paginator]:
        """Retrieve paginated dataset list."""
        # 1. Initialize paginator
        paginator = Paginator(db=self.db, req=req)

        # 2. Build query filters
        filters = [Dataset.account_id == account.id]
        if req.search_word.data:
            filters.append(Dataset.name.ilike(f"%{req.search_word.data}%"))

        # 3. Execute paginated query
        datasets = paginator.paginate(
            self.db.session.query(Dataset)
            .filter(*filters)
            .order_by(desc("created_at"))
        )

        return datasets, paginator

    def hit(self, dataset_id: UUID, req: HitReq, account: Account) -> list[dict]:
        """Run a retrieval test against the dataset."""
        # 1. Retrieve dataset and validate ownership
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise NotFoundException("The dataset does not exist.")

        # 2. Perform retrieval via retrieval service
        lc_documents = self.retrieval_service.search_in_datasets(
            dataset_ids=[dataset_id],
            account_id=account.id,
            **req.data,
        )
        lc_document_dict = {
            str(doc.metadata["segment_id"]): doc for doc in lc_documents
        }

        # 3. Query corresponding segments
        segments = self.db.session.query(Segment).filter(
            Segment.id.in_([
                str(doc.metadata["segment_id"]) for doc in lc_documents
            ])
        ).all()
        segment_dict = {str(segment.id): segment for segment in segments}

        # 4. Sort segments according to retrieval order
        sorted_segments = [
            segment_dict[str(doc.metadata["segment_id"])]
            for doc in lc_documents
            if str(doc.metadata["segment_id"]) in segment_dict
        ]

        # 5. Assemble response payload
        hit_result = []
        for segment in sorted_segments:
            document = segment.document
            upload_file = document.upload_file
            hit_result.append({
                "id": segment.id,
                "document": {
                    "id": document.id,
                    "name": document.name,
                    "extension": upload_file.extension,
                    "mime_type": upload_file.mime_type,
                },
                "dataset_id": segment.dataset_id,
                "score": lc_document_dict[str(segment.id)].metadata["score"],
                "position": segment.position,
                "content": segment.content,
                "keywords": segment.keywords,
                "character_count": segment.character_count,
                "token_count": segment.token_count,
                "hit_count": segment.hit_count,
                "enabled": segment.enabled,
                "disabled_at": datetime_to_timestamp(segment.disabled_at),
                "status": segment.status,
                "error": segment.error,
                "updated_at": datetime_to_timestamp(segment.updated_at),
                "created_at": datetime_to_timestamp(segment.created_at),
            })

        return hit_result

    def delete_dataset(self, dataset_id: UUID, account: Account) -> Dataset:
        """
        Delete a dataset and all associated data, including documents, segments,
        keywords, and vector database records.
        """
        # 1. Retrieve dataset and validate ownership
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise NotFoundException("The dataset does not exist.")

        try:
            # 2. Delete dataset record and application associations
            self.delete(dataset)
            with self.db.auto_commit():
                self.db.session.query(AppDatasetJoin).filter(
                    AppDatasetJoin.dataset_id == dataset_id,
                ).delete()

            # 3. Trigger async cleanup task
            delete_dataset.delay(dataset_id)

        except Exception as e:
            logging.exception(
                "Failed to delete dataset, dataset_id: %(dataset_id)s, error: %(error)s",
                {"dataset_id": dataset_id, "error": e},
            )
            raise FailException("Failed to delete dataset. Please try again later.")
