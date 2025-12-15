#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : segment_service.py
"""
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from injector import inject
from langchain_core.documents import Document as LCDocument
from redis import Redis
from sqlalchemy import asc, func

from internal.entity.cache_entity import LOCK_EXPIRE_TIME, LOCK_SEGMENT_UPDATE_ENABLED
from internal.entity.dataset_entity import DocumentStatus, SegmentStatus
from internal.exception import NotFoundException, FailException, ValidateErrorException
from internal.lib.helper import generate_text_hash
from internal.model import Document, Segment, Account
from internal.schema.segment_schema import (
    GetSegmentsWithPageReq,
    CreateSegmentReq,
    UpdateSegmentReq,
)
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .embeddings_service import EmbeddingsService
from .jieba_service import JiebaService
from .keyword_table_service import KeywordTableService
from .vector_database_service import VectorDatabaseService


@inject
@dataclass
class SegmentService(BaseService):
    """Segment service"""
    db: SQLAlchemy
    redis_client: Redis
    jieba_service: JiebaService
    embeddings_service: EmbeddingsService
    keyword_table_service: KeywordTableService
    vector_database_service: VectorDatabaseService

    def create_segment(
            self,
            dataset_id: UUID,
            document_id: UUID,
            req: CreateSegmentReq,
            account: Account,
    ) -> Segment:
        """Create a new document segment based on the provided input."""
        # 1. Validate token length; must not exceed 1000 tokens
        token_count = self.embeddings_service.calculate_token_count(req.content.data)
        if token_count > 1000:
            raise ValidateErrorException("Segment content must not exceed 1000 tokens.")

        # 2. Retrieve document and validate permissions
        document = self.get(Document, document_id)
        if (
                document is None
                or document.account_id != account.id
                or document.dataset_id != dataset_id
        ):
            raise NotFoundException(
                "The dataset document does not exist or you do not have permission to create a segment."
            )

        # 3. Only COMPLETED documents can accept new segments
        if document.status != DocumentStatus.COMPLETED:
            raise FailException("Segments cannot be added to this document right now. Please try again later.")

        # 4. Get the max segment position within the document
        position = self.db.session.query(func.coalesce(func.max(Segment.position), 0)).filter(
            Segment.document_id == document_id,
        ).scalar()

        # 5. If keywords are not provided, generate them via jieba
        if req.keywords.data is None or len(req.keywords.data) == 0:
            req.keywords.data = self.jieba_service.extract_keywords(req.content.data, 10)

        # 6. Insert record into Postgres
        segment = None
        try:
            # 7. position + 1 and create the segment record
            position += 1
            segment = self.create(
                Segment,
                account_id=account.id,
                dataset_id=dataset_id,
                document_id=document_id,
                node_id=uuid.uuid4(),
                position=position,
                content=req.content.data,
                character_count=len(req.content.data),
                token_count=token_count,
                keywords=req.keywords.data,
                hash=generate_text_hash(req.content.data),
                enabled=True,
                processing_started_at=datetime.now(),
                indexing_completed_at=datetime.now(),
                completed_at=datetime.now(),
                status=SegmentStatus.COMPLETED,
            )

            # 8. Insert into vector database
            self.vector_database_service.vector_store.add_documents(
                [LCDocument(
                    page_content=req.content.data,
                    metadata={
                        "account_id": str(document.account_id),
                        "dataset_id": str(document.dataset_id),
                        "document_id": str(document.id),
                        "segment_id": str(segment.id),
                        "node_id": str(segment.node_id),
                        "document_enabled": document.enabled,
                        "segment_enabled": True,
                    }
                )],
                ids=[str(segment.node_id)],
            )

            # 9. Recompute document-level total character and token counts
            document_character_count, document_token_count = self.db.session.query(
                func.coalesce(func.sum(Segment.character_count), 0),
                func.coalesce(func.sum(Segment.token_count), 0)
            ).filter(Segment.document_id == document.id).first()

            # 10. Update document stats
            self.update(
                document,
                character_count=document_character_count,
                token_count=document_token_count,
            )

            # 11. Update keyword table
            if document.enabled is True:
                self.keyword_table_service.add_keyword_table_from_ids(dataset_id, [segment.id])

        except Exception as e:
            logging.exception(
                "Exception occurred while building segment index, error: %(error)s",
                {"error": e},
            )
            if segment:
                self.update(
                    segment,
                    error=str(e),
                    status=SegmentStatus.ERROR,
                    enabled=False,
                    disabled_at=datetime.now(),
                    stopped_at=datetime.now(),
                )
            raise FailException("Failed to create segment. Please try again later.")

    def update_segment(
            self,
            dataset_id: UUID,
            document_id: UUID,
            segment_id: UUID,
            req: UpdateSegmentReq,
            account: Account
    ) -> Segment:
        """Update a specific document segment based on the provided input."""
        # 1. Retrieve segment and validate permissions
        segment = self.get(Segment, segment_id)
        if (
                segment is None
                or segment.account_id != account.id
                or segment.dataset_id != dataset_id
                or segment.document_id != document_id
        ):
            raise NotFoundException(
                "The segment does not exist or you do not have permission to modify it."
            )

        # 2. Only COMPLETED segments are editable
        if segment.status != SegmentStatus.COMPLETED:
            raise FailException("This segment cannot be modified right now. Please try again later.")

        # 3. If keywords are not provided, generate them via jieba
        if req.keywords.data is None or len(req.keywords.data) == 0:
            req.keywords.data = self.jieba_service.extract_keywords(req.content.data, 10)

        # 4. Compute hash to decide whether vector/document stats need updating
        new_hash = generate_text_hash(req.content.data)
        required_update = segment.hash != new_hash

        try:
            # 5. Update segment record
            self.update(
                segment,
                keywords=req.keywords.data,
                content=req.content.data,
                hash=new_hash,
                character_count=len(req.content.data),
                token_count=self.embeddings_service.calculate_token_count(req.content.data),
            )

            # 7. Refresh keyword table memberships for this segment
            self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [segment_id])
            self.keyword_table_service.add_keyword_table_from_ids(dataset_id, [segment_id])

            # 8. If content changed, update document stats + vector DB record
            if required_update:
                # 7. Update document stats
                document = segment.document
                document_character_count, document_token_count = self.db.session.query(
                    func.coalesce(func.sum(Segment.character_count), 0),
                    func.coalesce(func.sum(Segment.token_count), 0)
                ).filter(Segment.document_id == document.id).first()
                self.update(
                    document,
                    character_count=document_character_count,
                    token_count=document_token_count,
                )

                # 9. Update vector DB record
                self.vector_database_service.collection.data.update(
                    uuid=str(segment.node_id),
                    properties={
                        "text": req.content.data,
                    },
                    vector=self.embeddings_service.embeddings.embed_query(req.content.data)
                )
        except Exception as e:
            logging.exception(
                "Failed to update segment record, segment_id: %(segment_id)s, error: %(error)s",
                {"segment_id": segment_id, "error": e},
            )
            raise FailException("Failed to update segment record. Please try again later.")

        return segment

    def get_segments_with_page(
            self,
            dataset_id: UUID,
            document_id: UUID,
            req: GetSegmentsWithPageReq,
            account: Account,
    ) -> tuple[list[Segment], Paginator]:
        """Retrieve paginated segment list."""
        # 1. Retrieve document and validate permissions
        document = self.get(Document, document_id)
        if document is None or document.dataset_id != dataset_id or document.account_id != account.id:
            raise NotFoundException(
                "The dataset document does not exist or you do not have permission to view it."
            )

        # 2. Build paginator
        paginator = Paginator(db=self.db, req=req)

        # 3. Build filters
        filters = [Segment.document_id == document_id]
        if req.search_word.data:
            filters.append(Segment.content.ilike(f"%{req.search_word.data}%"))

        # 4. Execute paginated query
        segments = paginator.paginate(
            self.db.session.query(Segment).filter(*filters).order_by(asc("position"))
        )

        return segments, paginator

    def get_segment(self, dataset_id: UUID, document_id: UUID, segment_id: UUID, account: Account) -> Segment:
        """Retrieve a segment detail record."""
        # 1. Retrieve segment and validate permissions
        segment = self.get(Segment, segment_id)
        if (
                segment is None
                or segment.account_id != account.id
                or segment.dataset_id != dataset_id
                or segment.document_id != document_id
        ):
            raise NotFoundException(
                "The segment does not exist or you do not have permission to view it."
            )

        return segment

    def update_segment_enabled(
            self,
            dataset_id: UUID,
            document_id: UUID,
            segment_id: UUID,
            enabled: bool,
            account: Account
    ) -> Segment:
        """Update a segment's enabled/disabled status."""
        # 1. Retrieve segment and validate permissions
        segment = self.get(Segment, segment_id)
        if (
                segment is None
                or segment.account_id != account.id
                or segment.dataset_id != dataset_id
                or segment.document_id != document_id
        ):
            raise NotFoundException(
                "The segment does not exist or you do not have permission to modify it."
            )

        # 2. Only COMPLETED segments can be enabled/disabled
        if segment.status != SegmentStatus.COMPLETED:
            raise FailException("This segment cannot be modified right now. Please try again later.")

        # 3. If requested enabled state matches current state, raise error
        if enabled == segment.enabled:
            raise FailException(f"Invalid status update: segment is already {'enabled' if enabled else 'disabled'}.")

        # 4. Acquire lock for updating enabled state
        cache_key = LOCK_SEGMENT_UPDATE_ENABLED.format(segment_id=segment_id)
        cache_result = self.redis_client.get(cache_key)
        if cache_result is not None:
            raise FailException("This segment is currently being updated. Please try again later.")

        # 5. Lock and update Postgres, Weaviate, and keyword table
        with self.redis_client.lock(cache_key, LOCK_EXPIRE_TIME):
            try:
                # 6. Update segment enabled state in Postgres
                self.update(
                    segment,
                    enabled=enabled,
                    disabled_at=None if enabled else datetime.now()
                )

                # 7. Update keyword table membership
                document = segment.document
                if enabled is True and document.enabled is True:
                    self.keyword_table_service.add_keyword_table_from_ids(dataset_id, [segment_id])
                else:
                    self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [segment_id])

                # 8. Sync enabled state to vector DB
                self.vector_database_service.collection.data.update(
                    uuid=segment.node_id,
                    properties={"segment_enabled": enabled}
                )
            except Exception as e:
                logging.exception(
                    "Exception occurred while changing segment enabled status, segment_id: %(segment_id)s, error: %(error)s",
                    {"segment_id": segment_id, "error": e},
                )
                self.update(
                    segment,
                    error=str(e),
                    status=SegmentStatus.ERROR,
                    enabled=False,
                    disabled_at=datetime.now(),
                    stopped_at=datetime.now(),
                )
                raise FailException("Failed to update segment enabled status. Please try again later.")

        return segment

    def delete_segment(
            self,
            dataset_id: UUID,
            document_id: UUID,
            segment_id: UUID,
            account: Account
    ) -> Segment:
        """Delete a specific segment (synchronous)."""
        # 1. Retrieve segment and validate permissions
        segment = self.get(Segment, segment_id)
        if (
                segment is None
                or segment.account_id != account.id
                or segment.dataset_id != dataset_id
                or segment.document_id != document_id
        ):
            raise NotFoundException(
                "The segment does not exist or you do not have permission to modify it."
            )

        # 2. Only COMPLETED/ERROR segments can be deleted
        if segment.status not in [SegmentStatus.COMPLETED, SegmentStatus.ERROR]:
            raise FailException("This segment cannot be deleted right now. Please try again later.")

        # 3. Delete segment and fetch parent document
        document = segment.document
        self.delete(segment)

        # 4. Remove keywords for this segment from keyword table
        self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [segment_id])

        # 5. Delete vector DB record
        try:
            self.vector_database_service.collection.data.delete_by_id(str(segment.node_id))
        except Exception as e:
            logging.exception(
                "Failed to delete segment record, segment_id: %(segment_id)s, error: %(error)s",
                {"segment_id": segment_id, "error": e},
            )

        # 6. Recompute and update document-level counts
        document_character_count, document_token_count = self.db.session.query(
            func.coalesce(func.sum(Segment.character_count), 0),
            func.coalesce(func.sum(Segment.token_count), 0)
        ).filter(Segment.document_id == document.id).first()
        self.update(
            document,
            character_count=document_character_count,
            token_count=document_token_count,
        )

        return segment
