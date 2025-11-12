#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : document_service.py
"""
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from injector import inject
from redis import Redis
from sqlalchemy import desc, asc, func

from internal.entity.cache_entity import LOCK_DOCUMENT_UPDATE_ENABLED, LOCK_EXPIRE_TIME
from internal.entity.dataset_entity import ProcessType, DocumentStatus, SegmentStatus
from internal.entity.upload_file_entity import ALLOWED_DOCUMENT_EXTENSION
from internal.exception import ForbiddenException, FailException, NotFoundException
from internal.lib.helper import datetime_to_timestamp
from internal.model import Dataset, Document, Segment, UploadFile, ProcessRule, Account
from internal.schema.document_schema import GetDocumentsWithPageReq
from internal.task.document_task import build_documents, update_document_enabled, delete_document
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class DocumentService(BaseService):
    """Document Service"""
    db: SQLAlchemy
    redis_client: Redis

    def create_documents(
            self,
            dataset_id: UUID,
            upload_file_ids: list[UUID],
            process_type: str = ProcessType.AUTOMATIC,
            rule: dict = None,
            account: Account = None,
    ) -> tuple[list[Document], str]:
        """Create a list of documents based on the provided information and trigger asynchronous processing."""
        # 1. Verify dataset permission
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise ForbiddenException("The current user does not have access to this dataset or it does not exist.")

        # 2. Retrieve uploaded files and validate permissions and file extensions
        upload_files = self.db.session.query(UploadFile).filter(
            UploadFile.account_id == account.id,
            UploadFile.id.in_(upload_file_ids),
        ).all()

        upload_files = [
            upload_file for upload_file in upload_files
            if upload_file.extension.lower() in ALLOWED_DOCUMENT_EXTENSION
        ]

        if len(upload_files) == 0:
            logging.warning(
                f"No valid files found in uploaded list. "
                f"account_id: {str(account.id)}, dataset_id: {dataset_id}, upload_file_ids: {upload_file_ids}"
            )
            raise FailException("No valid document files found. Please re-upload.")

        # 3. Create a batch ID and processing rule record in the database
        batch = time.strftime("%Y%m%d%H%M%S") + str(random.randint(100000, 999999))
        process_rule = self.create(
            ProcessRule,
            account_id=account.id,
            dataset_id=dataset_id,
            mode=process_type,
            rule=rule,
        )

        # 4. Get the latest document position within the dataset
        position = self.get_latest_document_position(dataset_id)

        # 5. Iterate through valid uploaded files and create document records
        documents = []
        for upload_file in upload_files:
            position += 1
            document = self.create(
                Document,
                account_id=account.id,
                dataset_id=dataset_id,
                upload_file_id=upload_file.id,
                process_rule_id=process_rule.id,
                batch=batch,
                name=upload_file.name,
                position=position,
            )
            documents.append(document)

        # 6. Trigger an asynchronous task for subsequent processing
        build_documents.delay([document.id for document in documents])

        # 7. Return the document list and batch ID
        return documents, batch

    def get_documents_status(self, dataset_id: UUID, batch: str, account: Account) -> list[dict]:
        """Retrieve document status for a given dataset ID and batch identifier."""
        # 1. Verify dataset permission
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise ForbiddenException("The current user does not have access to this dataset or it does not exist.")

        # 2. Query the list of documents under the dataset for the given batch
        documents = self.db.session.query(Document).filter(
            Document.dataset_id == dataset_id,
            Document.batch == batch,
        ).order_by(asc("position")).all()
        if documents is None or len(documents) == 0:
            raise NotFoundException("No documents found for this batch. Please verify and try again.")

        # 3. Iterate through the document list and extract their status information
        documents_status = []
        for document in documents:
            # 4. Count total and completed segments for each document
            segment_count = self.db.session.query(func.count(Segment.id)).filter(
                Segment.document_id == document.id,
            ).scalar()
            completed_segment_count = self.db.session.query(func.count(Segment.id)).filter(
                Segment.document_id == document.id,
                Segment.status == SegmentStatus.COMPLETED,
            ).scalar()

            upload_file = document.upload_file
            documents_status.append({
                "id": document.id,
                "name": document.name,
                "size": upload_file.size,
                "extension": upload_file.extension,
                "mime_type": upload_file.mime_type,
                "position": document.position,
                "segment_count": segment_count,
                "completed_segment_count": completed_segment_count,
                "error": document.error,
                "status": document.status,
                "processing_started_at": datetime_to_timestamp(document.processing_started_at),
                "parsing_completed_at": datetime_to_timestamp(document.parsing_completed_at),
                "splitting_completed_at": datetime_to_timestamp(document.splitting_completed_at),
                "indexing_completed_at": datetime_to_timestamp(document.indexing_completed_at),
                "completed_at": datetime_to_timestamp(document.completed_at),
                "stopped_at": datetime_to_timestamp(document.stopped_at),
                "created_at": datetime_to_timestamp(document.created_at),
            })

        return documents_status

    def get_document(self, dataset_id: UUID, document_id: UUID, account: Account) -> Document:
        """Retrieve a specific document record by dataset ID and document ID."""
        document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("The specified document does not exist. Please verify and try again.")
        if document.dataset_id != dataset_id or document.account_id != account.id:
            raise ForbiddenException("The current user is not authorized to access this document.")

        return document

    def update_document(self, dataset_id: UUID, document_id: UUID, account: Account, **kwargs) -> Document:
        """Update document information by dataset ID and document ID."""
        document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("The specified document does not exist. Please verify and try again.")
        if document.dataset_id != dataset_id or document.account_id != account.id:
            raise ForbiddenException("The current user is not authorized to modify this document.")

        return self.update(document, **kwargs)

    def update_document_enabled(
            self,
            dataset_id: UUID,
            document_id: UUID,
            enabled: bool,
            account: Account,
    ) -> Document:
        """Update the enabled/disabled status of a document and trigger async vector database updates."""
        # 1. Retrieve document and verify permission
        document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("The specified document does not exist. Please verify and try again.")
        if document.dataset_id != dataset_id or document.account_id != account.id:
            raise ForbiddenException("The current user is not authorized to modify this document.")

        # 2. Only documents in COMPLETED state can have their enabled status changed
        if document.status != DocumentStatus.COMPLETED:
            raise ForbiddenException("The document is not in an editable state. Please try again later.")

        # 3. The new enabled state must be the opposite of the current state
        if document.enabled == enabled:
            raise FailException(f"Invalid operation: document is already {'enabled' if enabled else 'disabled'}.")

        # 4. Check for an active lock key in Redis to avoid concurrent updates
        cache_key = LOCK_DOCUMENT_UPDATE_ENABLED.format(document_id=document.id)
        cache_result = self.redis_client.get(cache_key)
        if cache_result is not None:
            raise FailException("The document’s enable state is being updated. Please try again later.")

        # 5. Update the enabled state and set the cache lock (expires in 600s)
        self.update(
            document,
            enabled=enabled,
            disabled_at=None if enabled else datetime.now(),
        )
        self.redis_client.setex(cache_key, LOCK_EXPIRE_TIME, 1)

        # 6. Trigger an asynchronous background task for vector DB updates
        update_document_enabled.delay(document.id)

        return document

    def delete_document(self, dataset_id: UUID, document_id: UUID, account: Account) -> Document:
        """Delete a document record by dataset ID and document ID, including related segments, keywords, and vector data."""
        # 1. Retrieve document and verify permission
        document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("The specified document does not exist. Please verify and try again.")
        if document.dataset_id != dataset_id or document.account_id != account.id:
            raise ForbiddenException("The current user is not authorized to delete this document.")

        # 2. Documents can only be deleted when in COMPLETED or ERROR state
        if document.status not in [DocumentStatus.COMPLETED, DocumentStatus.ERROR]:
            raise FailException("The document cannot be deleted at this time. Please wait until processing completes.")

        # 3. Delete the document’s base information from PostgreSQL
        self.delete(document)

        # 4. Trigger an asynchronous task to handle cleanup (keywords, segments, vector DB records, etc.)
        delete_document.delay(dataset_id, document_id)

        return document

    def get_documents_with_page(
            self, dataset_id: UUID, req: GetDocumentsWithPageReq, account: Account,
    ) -> tuple[list[Document], Paginator]:
        """Retrieve a paginated list of documents for a given dataset ID and query request."""
        # 1. Verify dataset permission
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise NotFoundException("The specified dataset does not exist or you do not have permission.")

        # 2. Initialize paginator
        paginator = Paginator(db=self.db, req=req)

        # 3. Build query filters
        filters = [
            Document.account_id == account.id,
            Document.dataset_id == dataset_id,
        ]
        if req.search_word.data:
            filters.append(Document.name.ilike(f"%{req.search_word.data}%"))

        # 4. Execute paginated query
        documents = paginator.paginate(
            self.db.session.query(Document).filter(*filters).order_by(desc("created_at"))
        )

        return documents, paginator

    def get_latest_document_position(self, dataset_id: UUID) -> int:
        """Retrieve the latest document position for a given dataset."""
        document = self.db.session.query(Document).filter(
            Document.dataset_id == dataset_id,
        ).order_by(desc("position")).first()
        return document.position if document else 0
