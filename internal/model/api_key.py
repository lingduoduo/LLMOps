#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : api_key.py
"""
from sqlalchemy import (
    Column,
    UUID,
    String,
    DateTime,
    Boolean,
    text,
    PrimaryKeyConstraint,
)

from internal.extension.database_extension import db
from .account import Account


class ApiKey(db.Model):
    """API Key Model"""
    __tablename__ = "api_key"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_api_key_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    # Record ID

    account_id = Column(UUID, nullable=False)
    # Associated account ID

    api_key = Column(String(255), nullable=False, server_default=text("''::character varying"))
    # Encrypted API key

    is_active = Column(Boolean, nullable=False, server_default=text('false'))
    # Whether the API key is active; only usable when true

    remark = Column(String(255), nullable=False, server_default=text("''::character varying"))
    # Remark / notes

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)')
    )
    # Timestamp updated automatically

    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))

    # Creation timestamp

    @property
    def account(self) -> "Account":
        """Read-only property that returns the account this API key belongs to"""
        return db.session.query(Account).get(self.account_id)
