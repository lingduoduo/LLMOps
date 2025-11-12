#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : indexing_service.py
"""
import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from flask import Flask, current_app
from injector import inject
from langchain_core.documents import Document as LCDocument
from redis import Redis
from sqlalchemy import func
from weaviate.classes.query import Filter

from internal.core.file_extractor import FileExtractor
from internal.entity.cache_entity import (
    LOCK_DOCUMENT_UPDATE_ENABLED
)
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
    """Index building service"""
    db: SQLAlchemy
    redis_client: Redis
    file_extractor: FileExtractor
    process_rule_service: ProcessRuleService
    embeddings_service: EmbeddingsService
    jieba_service: JiebaService
    keyword_table_service: KeywordTableService
    vector_database_service: VectorDatabaseService

    def build_documents(self, document_ids: list[UUID]) -> None:
        """Build knowledge-base documents from the given IDs: load → split → index → store."""
        # 1) Fetch all documents by IDs
        documents = self.db.session.query(Document).filter(
            Document.id.in_(document_ids)
        ).all()

        # 2) Iterate and build each document
        for document in documents:
            try:
                # 3) Set status to PARSING and record start time
                self.update(document, status=DocumentStatus.PARSING, processing_started_at=datetime.now())

                # 4) Load LangChain documents and update status/timestamps
                lc_documents = self._parsing(document)

                # 5) Split documents into segments and update status/timestamps
                lc_segments = self._splitting(document, lc_documents)

                # 6) Build index: keyword extraction & keyword table updates
                self._indexing(document, lc_segments)

                # 7) Persist: update statuses and write to vector database
                self._completed(document, lc_segments)

            except Exception as e:
                logging.exception(f"Error building document: {str(e)}")
                self.update(
                    document,
                    status=DocumentStatus.ERROR,
                    error=str(e),
                    stopped_at=datetime.now(),
                )

    def update_document_enabled(self, document_id: UUID) -> None:
        """Update a document's enabled status and synchronize records in the vector database."""
        # 1) Build cache key
        cache_key = LOCK_DOCUMENT_UPDATE_ENABLED.format(document_id=document_id)

        # 2) Fetch the document
        document = self.get(Document, document_id)
        if document is None:
            logging.exception(f"Document not found, document_id: {document_id}")
            raise NotFoundException("Document does not exist")

        # 3) Query all segment node IDs for this document
        segments = self.db.session.query(Segment).with_entities(Segment.id, Segment.node_id, Segment.enabled).filter(
            Segment.document_id == document_id,
            Segment.status == SegmentStatus.COMPLETED,
        ).all()
        segment_ids = [id for id, _, _ in segments]
        node_ids = [node_id for _, node_id, _ in segments]
        try:
            # 4) Update vector database records for each node_id
            collection = self.vector_database_service.collection
            for node_id in node_ids:
                try:
                    collection.data.update(
                        uuid=node_id,
                        properties={
                            "document_enabled": document.enabled,
                        }
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

            # 5) Update keyword table (enabled=False → remove; enabled=True → add)
            if document.enabled is True:
                # 6) Switched from disabled to enabled: add keywords for enabled segments
                enabled_segment_ids = [id for id, _, enabled in segments if enabled is True]
                self.keyword_table_service.add_keyword_table_from_ids(document.dataset_id, enabled_segment_ids)
            else:
                # 7) Switched from enabled to disabled: remove keywords
                self.keyword_table_service.delete_keyword_table_from_ids(document.dataset_id, segment_ids)
        except Exception as e:
            # 5) Log and revert the document's enabled status
            logging.exception(f"Failed to update document enabled status in vector DB, "
                              f"document_id: {document_id}, error: {str(e)}")
            origin_enabled = not document.enabled
            self.update(
                document,
                enabled=origin_enabled,
                disabled_at=None if origin_enabled else datetime.now(),
            )
        finally:
            # 6) Clear the cache key indicating the async operation is finished (success or failure)
            self.redis_client.delete(cache_key)

    def delete_document(self, dataset_id: UUID, document_id: UUID) -> None:
        """Delete a document by dataset_id and document_id."""
        # 1) Gather all segment IDs under this document
        segment_ids = [
            str(id) for id, in self.db.session.query(Segment).with_entities(Segment.id).filter(
                Segment.document_id == document_id,
            ).all()
        ]

        # 2) Delete associated records from the vector database
        collection = self.vector_database_service.collection
        collection.data.delete_many(
            where=Filter.by_property("document_id").equal(document_id),
        )

        # 3) Delete related segment records from Postgres
        with self.db.auto_commit():
            self.db.session.query(Segment).filter(
                Segment.document_id == document_id,
            ).delete()

        # 4) Remove keywords mapped to these segment IDs
        self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, segment_ids)

    def delete_dataset(self, dataset_id: UUID) -> None:
        """Delete all data related to the given dataset_id."""
        try:
            with self.db.auto_commit():
                # 1) Delete related documents
                self.db.session.query(Document).filter(
                    Document.dataset_id == dataset_id,
                ).delete()

                # 2) Delete related segments
                self.db.session.query(Segment).filter(
                    Segment.dataset_id == dataset_id,
                ).delete()

                # 3) Delete keyword table records
                self.db.session.query(KeywordTable).filter(
                    KeywordTable.dataset_id == dataset_id,
                ).delete()

                # 4) Delete dataset query logs
                self.db.session.query(DatasetQuery).filter(
                    DatasetQuery.dataset_id == dataset_id,
                ).delete()

            # 5) Delete related vector database records
            self.vector_database_service.collection.data.delete_many(
                where=Filter.by_property("dataset_id").equal(str(dataset_id))
            )
        except Exception as e:
            logging.exception(f"Error asynchronously deleting dataset-related contents, "
                              f"dataset_id: {dataset_id}, error: {str(e)}")

    def _parsing(self, document: Document) -> list[LCDocument]:
        """Parse the given document into a list of LangChain Documents."""
        # 1) Load the UploadFile as LangChain Documents
        upload_file = document.upload_file
        lc_documents = self.file_extractor.load(upload_file, False, True)

        # 2) Clean extra whitespace/invalid characters
        for lc_document in lc_documents:
            lc_document.page_content = self._clean_extra_text(lc_document.page_content)

        # 3) Update document status and timestamps
        self.update(
            document,
            character_count=sum([len(lc_document.page_content) for lc_document in lc_documents]),
            status=DocumentStatus.SPLITTING,
            parsing_completed_at=datetime.now(),
        )

        return lc_documents

    def _splitting(self, document: Document, lc_documents: list[LCDocument]) -> list[LCDocument]:
        """Split documents into smaller segments based on the process rule."""
        # 1) Get text splitter from the process rule
        process_rule = document.process_rule
        text_splitter = self.process_rule_service.get_text_splitter_by_process_rule(
            process_rule,
            self.embeddings_service.calculate_token_count,
        )

        # 2) Clean text per the process rule
        for lc_document in lc_documents:
            lc_document.page_content = self.process_rule_service.clean_text_by_process_rule(
                lc_document.page_content,
                process_rule,
            )

        # 3) Split documents into segments
        lc_segments = text_splitter.split_documents(lc_documents)

        # 4) Get the max existing segment position for this document
        position = self.db.session.query(func.coalesce(func.max(Segment.position), 0)).filter(
            Segment.document_id == document.id,
        ).scalar()

        # 5) Persist segment metadata to Postgres and attach metadata to LC docs
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

        # 6) Update document status and token count
        self.update(
            document,
            token_count=sum([segment.token_count for segment in segments]),
            status=DocumentStatus.INDEXING,
            splitting_completed_at=datetime.now(),
        )

        return lc_segments

    def _indexing(self, document: Document, lc_segments: list[LCDocument]) -> None:
        """Build the index: extract keywords and update the keyword table."""
        for lc_segment in lc_segments:
            # 1) Extract up to 10 keywords per segment
            keywords = self.jieba_service.extract_keywords(lc_segment.page_content, 10)

            # 2) Update the segment's keywords
            self.db.session.query(Segment).filter(
                Segment.id == lc_segment.metadata["segment_id"]
            ).update({
                "keywords": keywords,
                "status": SegmentStatus.INDEXING,
                "indexing_completed_at": datetime.now(),
            })

            # 3) Fetch the dataset's keyword table
            keyword_table_record = self.keyword_table_service.get_keyword_table_from_dataset_id(document.dataset_id)
            keyword_table = {
                field: set(value) for field, value in keyword_table_record.keyword_table.items()
            }

            # 4) Add new keywords → segment_id mapping
            for keyword in keywords:
                if keyword not in keyword_table:
                    keyword_table[keyword] = set()
                keyword_table[keyword].add(lc_segment.metadata["segment_id"])

            # 5) Persist keyword table
            self.update(
                keyword_table_record,
                keyword_table={field: list(value) for field, value in keyword_table.items()}
            )

        # 6) Update document timestamps
        self.update(
            document,
            indexing_completed_at=datetime.now(),
        )

    def _completed(self, document: Document, lc_segments: list[LCDocument]) -> None:
        """Store segments in the vector database and finalize statuses."""
        # 1) Mark segments (and document) as enabled in the LC docs metadata
        for lc_segment in lc_segments:
            lc_segment.metadata["document_enabled"] = True
            lc_segment.metadata["segment_enabled"] = True

        # 2) Write to vector DB in batches of 10 to avoid oversized payloads
        def thread_func(flask_app: Flask, chunks: list[LCDocument], ids: list[UUID]) -> None:
            """Thread function to persist to the vector database and Postgres."""
            with flask_app.app_context():
                try:
                    self.vector_database_service.vector_store.add_documents(
                        chunks, ids=ids,
                    )
                    with self.db.auto_commit():
                        self.db.session.query(Segment).filter(
                            Segment.node_id.in_(ids)
                        ).update({
                            "status": SegmentStatus.COMPLETED,
                            "completed_at": datetime.now(),
                            "enabled": True,
                        })
                except Exception as e:
                    logging.exception(f"Exception while building segment index: {str(e)}")
                    with self.db.auto_commit():
                        self.db.session.query(Segment).filter(
                            Segment.node_id.in_(ids)
                        ).update({
                            "status": SegmentStatus.ERROR,
                            "completed_at": None,
                            "stopped_at": datetime.now(),
                            "enabled": False,
                        })

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(0, len(lc_segments), 10):
                chunks = lc_segments[i:i + 10]
                ids = [chunk.metadata["node_id"] for chunk in chunks]
                futures.append(executor.submit(thread_func, current_app._get_current_object(), chunks, ids))

            for future in futures:
                future.result()

        # 6) Update document status
        self.update(
            document,
            status=DocumentStatus.COMPLETED,
            completed_at=datetime.now(),
            enabled=True,
        )

    @classmethod
    def _clean_extra_text(cls, text: str) -> str:
        """Clean/remove extra or invalid characters from the text."""
        text = re.sub(r'<\|', '<', text)
        text = re.sub(r'\|>', '>', text)
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\xEF\xBF\xBE]', '', text)
        text = re.sub('\uFFFE', '', text)  # Remove invalid/zero-width characters
        return text
