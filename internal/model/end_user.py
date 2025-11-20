#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : end_user.py
"""
from sqlalchemy import (
    Column,
    UUID,
    DateTime,
    text,
    PrimaryKeyConstraint
)

from internal.extension.database_extension import db


class EndUser(db.Model):
    """End-user table model"""
    __tablename__ = "end_user"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_end_user_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    # End-user ID

    tenant_id = Column(UUID, nullable=False)
    # Tenant/account/space ID to which this user belongs

    app_id = Column(UUID, nullable=False)
    # Application ID; end users can only operate within the associated application

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)')
    )
    # Timestamp automatically updated on modification

    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))
    # Record creation timestamp
