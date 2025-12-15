#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : end_user.py
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    UUID,
    DateTime,
    text,
    PrimaryKeyConstraint,
    Index,
)

from internal.extension.database_extension import db


class EndUser(db.Model):
    """End user model"""
    __tablename__ = "end_user"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_end_user_id"),
        Index("end_user_tenant_id_idx", "tenant_id"),
        Index("end_user_app_id_idx", "app_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # End-user ID
    tenant_id = Column(UUID, nullable=False)  # Owning tenant / account / workspace ID
    app_id = Column(UUID, nullable=False)  # Associated application ID; end users can only access within an app
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=datetime.now,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))
