#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : upload_file_service.py
"""
from dataclasses import dataclass

from injector import inject

from internal.model import UploadFile
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class UploadFileService(BaseService):
    """Service for managing uploaded file records"""
    db: SQLAlchemy

    def create_upload_file(self, **kwargs) -> UploadFile:
        """Create a new file upload record"""
        return self.create(UploadFile, **kwargs)
