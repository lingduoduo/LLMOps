#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : demo_task.py
"""
import logging
import time
from uuid import UUID

from celery import shared_task
from flask import current_app


@shared_task
def demo_task(id: UUID) -> str:
    """Demo asynchronous task"""
    logging.info("Sleeping for 5 seconds")
    time.sleep(5)
    logging.info(f"Value of id: {id}")
    logging.info(f"Configuration info: {current_app.config}")
    return "Ling"
