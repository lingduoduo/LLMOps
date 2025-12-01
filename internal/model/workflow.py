#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : workflow.py
"""
from sqlalchemy import (
    Column,
    UUID,
    String,
    Text,
    Boolean,
    DateTime,
    Float,
    text,
    PrimaryKeyConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from internal.extension.database_extension import db


class Workflow(db.Model):
    """Workflow model"""
    __tablename__ = "workflow"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_workflow_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    account_id = Column(UUID, nullable=False)  # ID of the account that created the workflow
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Workflow name
    tool_call_name = Column(String(255), nullable=False,
                            server_default=text("''::character varying"))  # Workflow tool call name
    icon = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Workflow icon
    description = Column(Text, nullable=False, server_default=text("''::text"))  # Workflow description
    graph = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Runtime configuration
    draft_graph = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Draft graph configuration
    is_debug_passed = Column(Boolean, nullable=False, server_default=text("false"))  # Whether debugging has passed
    status = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Workflow status
    published_at = Column(DateTime, nullable=True)  # Publish time
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))


class WorkflowResult(db.Model):
    """Workflow result storage model"""
    __tablename__ = "workflow_result"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_workflow_result_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # Result ID
    app_id = Column(UUID, nullable=True)  # App ID that invoked the workflow; null means it wasn't invoked by an app
    account_id = Column(UUID, nullable=False)  # ID of the account that created the workflow
    workflow_id = Column(UUID, nullable=False)  # ID of the workflow associated with this result
    graph = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Runtime configuration
    state = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Final workflow state
    latency = Column(Float, nullable=False, server_default=text("0.0"))  # Total latency of the message
    status = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Execution status
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))
