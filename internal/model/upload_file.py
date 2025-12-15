#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : upload_file.py
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    UUID,
    String,
    Integer,
    DateTime,
    text,
    PrimaryKeyConstraint,
    Index,
)

from internal.extension.database_extension import db


class UploadFile(db.Model):
    """Uploaded file model"""
    __tablename__ = "upload_file"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_upload_file_id"),
        Index("upload_file_account_id_idx", "account_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    account_id = Column(UUID, nullable=False)  # Owning account ID
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Original file name
    key = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Storage key / path
    size = Column(Integer, nullable=False, server_default=text("0"))  # File size in bytes
    extension = Column(String(255), nullable=False, server_default=text("''::character varying"))  # File extension
    mime_type = Column(String(255), nullable=False, server_default=text("''::character varying"))  # MIME type
    hash = Column(String(255), nullable=False, server_default=text("''::character varying"))  # File hash (e.g. MD5/SHA)
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=datetime.now,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))
