#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : api_key.py
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    UUID,
    String,
    DateTime,
    Boolean,
    text,
    PrimaryKeyConstraint,
    Index,
)

from internal.extension.database_extension import db
from .account import Account


class ApiKey(db.Model):
    """API key model"""
    __tablename__ = "api_key"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_api_key_id"),
        Index("api_key_account_id_idx", "account_id"),
        Index("api_key_api_key_idx", "api_key"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # Record ID
    account_id = Column(UUID, nullable=False)  # Associated account ID
    api_key = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # Encrypted API key
    is_active = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )  # Whether the API key is active
    remark = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # Remark / description
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=datetime.now,
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
    )

    @property
    def account(self) -> "Account":
        """Read-only property: return the account this API key belongs to."""
        return db.session.query(Account).get(self.account_id)
