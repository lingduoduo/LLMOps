#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : indexing_service.py
"""
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from injector import inject
from langchain_core.documents import Document as LCDocument
from redis import Redis
from sqlalchemy import func
from weaviate.classes.query import Filter

from internal.core.file_extractor import FileExtractor
from internal.entity.cache_entity import LOCK_DOCUMENT_UPDATE_ENABLED
from internal.entity.dataset_entity import DocumentStatus, SegmentStatus
from internal.exception import NotFoundException
from internal.lib.helper import generate_text_hash
from internal.model import Document, Segment, KeywordTable, DatasetQuery
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .embeddings_service import EmbeddingsService
from .jieba_service import JiebaService
from .keyword_table_service import KeywordTableService
from .process_rule_service import ProcessRuleService
from .vector_database_service import VectorDatabaseService


@inject
@dataclass
class IndexingService(BaseService):
    """Index building service."""
    db: SQLAlchemy
    redis_client: Redis
    file_extractor: FileExtractor
    process_rule_service: ProcessRuleService
    embeddings_service: EmbeddingsService
    jieba_service: JiebaService
    keyword_table_service: KeywordTableService
    vector_database_service: VectorDatabaseService

    def build_documents(self, document_ids: list[UUID]) -> None:
        """Build knowledge-base documents for the given list of document IDs.

        This includes loading, splitting, building indexes, and storing data.
        """
        # 1. Fetch all documents by the given IDs
        documents = (
            self.db.session.query(Document)
            .filter(Document.id.in_(document_ids))
            .all()
        )

        # 2. Iterate through all documents and build each one
        for document in documents:
            try:
                # 3. Update current status to PARSING and record the start time
                self.update(
                    document,
                    status=DocumentStatus.PARSING,
                    processing_started_at=datetime.now(),
                )

                # 4. Parse/load the document and update document status/time
                lc_documents = self._parsing(document)

                # 5. Split the document into segments and update status/time
                lc_segments = self._splitting(document, lc_documents)

                # 6. Build indexes (keywords, vectors) and update status
                self._indexing(document, lc_segments)

                # 7. Persist results (update document status + store vectors)
                self._completed(document, lc_segments)

            except Exception as e:
                logging.exception(
                    "Error occurred while building the document. Error: %(error)s",
                    {"error": e},
                )
                self.update(
                    document,
                    status=DocumentStatus.ERROR,
                    error=str(e),
                    stopped_at=datetime.now(),
                )

    def update_document_enabled(self, document_id: UUID) -> None:
        """Update a document's enabled status and sync the change to Weaviate."""
        # 1. Build the cache key
        cache_key = LOCK_DOCUMENT_UPDATE_ENABLED.format(document_id=document_id)

        # 2. Fetch the document record by document_id
        document = self.get(Document, document_id)
        if document is None:
            logging.exception(
                "Document does not exist. document_id: %(document_id)s",
                {"document_id": document_id},
            )
            raise NotFoundException("Document does not exist")

        # 3. Query node IDs for all completed segments under this document
        segments = (
            self.db.session.query(Segment)
            .with_entities(Segment.id, Segment.node_id, Segment.enabled)
            .filter(
                Segment.document_id == document_id,
                Segment.status == SegmentStatus.COMPLETED,
            )
            .all()
        )
        segment_ids = [id for id, _, _ in segments]
        node_ids = [node_id for _, node_id, _ in segments]

        try:
            # 4. Loop through all node_ids and update vector records
            collection = self.vector_database_service.collection
            for node_id in node_ids:
                try:
                    collection.data.update(
                        uuid=node_id,
                        properties={
                            "document_enabled": document.enabled,
                        },
                    )
                except Exception as e:
                    with self.db.auto_commit():
                        self.db.session.query(Segment).filter(
                            Segment.node_id == node_id,
                        ).update({
                            "error": str(e),
                            "status": SegmentStatus.ERROR,
                            "enabled": False,
                            "disabled_at": datetime.now(),
                            "stopped_at": datetime.now(),
                        })

            # 5. Update keyword table accordingly
            #    (enabled=False => remove keywords; enabled=True => add keywords)
            if document.enabled is True:
                # 6. Switching from disabled to enabled: add keywords back
                enabled_segment_ids = [id for id, _, enabled in segments if enabled is True]
                self.keyword_table_service.add_keyword_table_from_ids(
                    document.dataset_id,
                    enabled_segment_ids,
                )
            else:
                # 7. Switching from enabled to disabled: remove keywords
                self.keyword_table_service.delete_keyword_table_from_ids(
                    document.dataset_id,
                    segment_ids,
                )

        except Exception as e:
            # 5. Log the error and revert enabled status back to the original value
            logging.exception(
                "Failed to update document enabled status in vector DB. "
                "document_id: %(document_id)s, error: %(error)s",
                {"document_id": document_id, "error": e},
            )
            origin_enabled = not document.enabled
            self.update(
                document,
                enabled=origin_enabled,
                disabled_at=None if origin_enabled else datetime.now(),
            )

        finally:
            # 6. Clear the cache key to indicate the async task is completed
            self.redis_client.delete(cache_key)

    def delete_document(self, dataset_id: UUID, document_id: UUID) -> None:
        """Delete a document by dataset_id + document_id."""
        # 1. Find all segment IDs under the document
        segment_ids = [
            str(id) for id, in (
                self.db.session.query(Segment)
                .with_entities(Segment.id)
                .filter(Segment.document_id == document_id)
                .all()
            )
        ]

        # 2. Delete associated records in the vector database
        collection = self.vector_database_service.collection
        collection.data.delete_many(
            where=Filter.by_property("document_id").equal(document_id),
        )

        # 3. Delete related segment records in Postgres
        with self.db.auto_commit():
            self.db.session.query(Segment).filter(
                Segment.document_id == document_id,
            ).delete()

        # 4. Delete keyword records for the segment IDs
        self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, segment_ids)

    def delete_dataset(self, dataset_id: UUID) -> None:
        """Delete a dataset and all associated records."""
        try:
            with self.db.auto_commit():
                # 1. Delete associated document records
                self.db.session.query(Document).filter(
                    Document.dataset_id == dataset_id,
                ).delete()

                # 2. Delete associated segment records
                self.db.session.query(Segment).filter(
                    Segment.dataset_id == dataset_id,
                ).delete()

                # 3. Delete associated keyword table records
                self.db.session.query(KeywordTable).filter(
                    KeywordTable.dataset_id == dataset_id,
                ).delete()

                # 4. Delete dataset query records
                self.db.session.query(DatasetQuery).filter(
                    DatasetQuery.dataset_id == dataset_id,
                ).delete()

            # 5. Delete associated records in the vector database
            self.vector_database_service.collection.data.delete_many(
                where=Filter.by_property("dataset_id").equal(str(dataset_id)),
            )

        except Exception as e:
            logging.exception(
                "Error occurred while asynchronously deleting dataset-related content. "
                "dataset_id: %(dataset_id)s, error: %(error)s",
                {"dataset_id": dataset_id, "error": e},
            )

    def _parsing(self, document: Document) -> list[LCDocument]:
        """Parse the given document into a list of LangChain documents."""
        # 1. Get upload_file and load LangChain documents
        upload_file = document.upload_file
        lc_documents = self.file_extractor.load(upload_file, False, True)

        # 2. Clean extra whitespace/text for each LangChain document
        for lc_document in lc_documents:
            lc_document.page_content = self._clean_extra_text(lc_document.page_content)

        # 3. Update document status and record timestamps
        self.update(
            document,
            character_count=sum(len(lc_document.page_content) for lc_document in lc_documents),
            status=DocumentStatus.SPLITTING,
            parsing_completed_at=datetime.now(),
        )

        return lc_documents

    def _splitting(self, document: Document, lc_documents: list[LCDocument]) -> list[LCDocument]:
        """Split documents into smaller segments based on the processing rule."""
        try:
            # 1. Get text splitter based on process_rule
            process_rule = document.process_rule
            text_splitter = self.process_rule_service.get_text_splitter_by_process_rule(
                process_rule,
                self.embeddings_service.calculate_token_count,
            )

            # 2. Clean text according to process_rule
            for lc_document in lc_documents:
                lc_document.page_content = self.process_rule_service.clean_text_by_process_rule(
                    lc_document.page_content,
                    process_rule,
                )

            # 3. Split documents into segments
            lc_segments = text_splitter.split_documents(lc_documents)

            # 4. Get the maximum segment position for the document
            position = (
                self.db.session.query(func.coalesce(func.max(Segment.position), 0))
                .filter(Segment.document_id == document.id)
                .scalar()
            )

            # 5. Process segments, attach metadata, and store them in Postgres
            segments = []
            for lc_segment in lc_segments:
                position += 1
                content = lc_segment.page_content
                segment = self.create(
                    Segment,
                    account_id=document.account_id,
                    dataset_id=document.dataset_id,
                    document_id=document.id,
                    node_id=uuid.uuid4(),
                    position=position,
                    content=content,
                    character_count=len(content),
                    token_count=self.embeddings_service.calculate_token_count(content),
                    hash=generate_text_hash(content),
                    status=SegmentStatus.WAITING,
                )
                lc_segment.metadata = {
                    "account_id": str(document.account_id),
                    "dataset_id": str(document.dataset_id),
                    "document_id": str(document.id),
                    "segment_id": str(segment.id),
                    "node_id": str(segment.node_id),
                    "document_enabled": False,
                    "segment_enabled": False,
                }
                segments.append(segment)

            # 6. Update document fields: status, token_count, timestamps, etc.
            self.update(
                document,
                token_count=sum(segment.token_count for segment in segments),
                status=DocumentStatus.INDEXING,
                splitting_completed_at=datetime.now(),
            )

            return lc_segments

        except Exception as e:
            print("Exception in _splitting:", e)

    def _indexing(self, document: Document, lc_segments: list[LCDocument]) -> None:
        """Build indexes for the segments, including keyword extraction and keyword table updates."""
        for lc_segment in lc_segments:
            # 1. Extract up to 10 keywords for each segment
            keywords = self.jieba_service.extract_keywords(lc_segment.page_content, 10)

            # 2. Update segment keywords and status
            self.db.session.query(Segment).filter(
                Segment.id == lc_segment.metadata["segment_id"],
            ).update({
                "keywords": keywords,
                "status": SegmentStatus.INDEXING,
                "indexing_completed_at": datetime.now(),
            })

            # 3. Get the keyword table for the dataset
            keyword_table_record = self.keyword_table_service.get_keyword_table_from_dataset_id(
                document.dataset_id,
            )
            keyword_table = {
                field: set(value) for field, value in keyword_table_record.keyword_table.items()
            }

            # 4. Add new keywords to the keyword table
            for keyword in keywords:
                if keyword not in keyword_table:
                    keyword_table[keyword] = set()
                keyword_table[keyword].add(lc_segment.metadata["segment_id"])

            # 5. Update the keyword table record
            self.update(
                keyword_table_record,
                keyword_table={field: list(value) for field, value in keyword_table.items()},
            )

        # 6. Update document timestamp/status
        self.update(
            document,
            indexing_completed_at=datetime.now(),
        )

    def _completed(self, document: Document, lc_segments: list[LCDocument]) -> None:
        """Store segments in the vector database and mark the document as completed."""
        # 1. Mark document and segment status as enabled for all segments
        for lc_segment in lc_segments:
            lc_segment.metadata["document_enabled"] = True
            lc_segment.metadata["segment_enabled"] = True

        # 2. Write to the vector DB in batches of 10 to avoid oversized requests
        try:
            for i in range(0, len(lc_segments), 10):
                chunks = lc_segments[i:i + 10]
                ids = [chunk.metadata["node_id"] for chunk in chunks]
                self.vector_database_service.vector_store.add_documents(chunks, ids=ids)
                with self.db.auto_commit():
                    self.db.session.query(Segment).filter(
                        Segment.node_id.in_(ids),
                    ).update({
                        "status": SegmentStatus.COMPLETED,
                        "completed_at": datetime.now(),
                        "enabled": True,
                    })

        except Exception as e:
            logging.exception(
                "Exception occurred while building segment indexes. Error: %(error)s",
                {"error": e},
            )
            with self.db.auto_commit():
                self.db.session.query(Segment).filter(
                    Segment.node_id.in_(ids),
                ).update({
                    "status": SegmentStatus.ERROR,
                    "completed_at": None,
                    "stopped_at": datetime.now(),
                    "enabled": False,
                    "error": str(e),
                })

        # 6. Update document status fields
        self.update(
            document,
            status=DocumentStatus.COMPLETED,
            completed_at=datetime.now(),
            enabled=True,
        )

    @classmethod
    def _clean_extra_text(cls, text: str) -> str:
        """Remove unwanted whitespace and special characters from the given text."""
        text = re.sub(r'<\|', '<', text)
        text = re.sub(r'\|>', '>', text)
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\xEF\xBF\xBE]', '', text)
        text = re.sub('\uFFFE', '', text)  # Remove zero-width non-character
        return text
