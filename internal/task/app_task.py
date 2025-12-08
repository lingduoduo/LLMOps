#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : app_task.py
"""
from uuid import UUID

from celery import shared_task


@shared_task
def auto_create_app(
        name: str,
        description: str,
        account_id: UUID,
) -> None:
    from app.http.module import injector
    from internal.service import AppService

    app_service = injector.get(AppService)
    app_service.auto_create_app(name, description, account_id)
