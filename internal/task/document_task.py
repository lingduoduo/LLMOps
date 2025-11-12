#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : document_task.py
"""
from uuid import UUID

from celery import shared_task


@shared_task
def build_documents(document_ids: list[UUID]) -> None:
    """Build documents based on the provided list of document IDs."""
    from app.http.module import injector
    from internal.service.indexing_service import IndexingService

    indexing_service = injector.get(IndexingService)
    indexing_service.build_documents(document_ids)


@shared_task
def update_document_enabled(document_id: UUID) -> None:
    """Update a document's enabled/disabled status by its ID."""
    from app.http.module import injector
    from internal.service.indexing_service import IndexingService

    indexing_service = injector.get(IndexingService)
    indexing_service.update_document_enabled(document_id)


@shared_task
def delete_document(dataset_id: UUID, document_id: UUID) -> None:
    """Delete a document record using the dataset ID and document ID."""
    from app.http.module import injector
    from internal.service.indexing_service import IndexingService

    indexing_service = injector.get(IndexingService)
    indexing_service.delete_document(dataset_id, document_id)
