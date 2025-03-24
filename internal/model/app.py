#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : app.py
"""
from sqlalchemy import (
    Column,
    UUID,
    String,
    Text,
    DateTime,
    PrimaryKeyConstraint,
    Index,
    text,
)

from internal.extension.database_extension import db


class App(db.Model):
    """AI Application Base Model"""
    __tablename__ = "app"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_id"),  # Primary key constraint for the "id" column
        Index("idx_app_account_id", "account_id"),  # Index on the "account_id" column
    )

    # Unique identifier (UUID) for the app
    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))

    # Reference to an account, represented as a UUID
    account_id = Column(UUID)

    # Application name (max 255 characters)
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))

    # URL or path for the application icon (max 255 characters)
    icon = Column(String(255), nullable=False, server_default=text("''::character varying"))

    # Description of the application (text field)
    description = Column(Text, nullable=False, server_default=text("''::text"))

    # Application status (e.g., active, inactive)
    status = Column(String(255), nullable=False, server_default=text("''::character varying"))

    # Timestamp for when the record was last updated
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),  # Auto-update on row modification
    )

    # Timestamp for when the record was created
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))
