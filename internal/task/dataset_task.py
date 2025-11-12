#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : dataset_task.py
"""
from uuid import UUID

from celery import shared_task


@shared_task
def delete_dataset(dataset_id: UUID) -> None:
    """Delete the specified dataset by its ID."""
    from app.http.module import injector
    from internal.service import IndexingService

    indexing_service = injector.get(IndexingService)
    indexing_service.delete_dataset(dataset_id)
