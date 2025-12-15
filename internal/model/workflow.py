#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : workflow.py
"""
from datetime import datetime

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
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB

from internal.extension.database_extension import db


class Workflow(db.Model):
    """Workflow model"""
    __tablename__ = "workflow"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_workflow_id"),
        Index("workflow_account_id_idx", "account_id"),
        Index("workflow_tool_call_name_idx", "tool_call_name"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    account_id = Column(UUID, nullable=False)  # Creator account ID
    name = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # Workflow name
    tool_call_name = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # Tool-call name exposed to LLM / agent
    icon = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # Workflow icon
    description = Column(
        Text,
        nullable=False,
        server_default=text("''::text"),
    )  # Workflow description
    graph = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )  # Published / runtime graph configuration
    draft_graph = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )  # Draft graph configuration
    is_debug_passed = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )  # Whether debugging has passed
    status = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # Workflow status (e.g. draft / published)
    published_at = Column(DateTime, nullable=True)  # Publish timestamp
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


class WorkflowResult(db.Model):
    """Workflow execution result model"""
    __tablename__ = "workflow_result"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_workflow_result_id"),
        Index("workflow_result_app_id_idx", "app_id"),
        Index("workflow_result_account_id_idx", "account_id"),
        Index("workflow_result_workflow_id_idx", "workflow_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # Result ID
    app_id = Column(
        UUID,
        nullable=True,
    )  # Calling app ID; None means non-app invocation
    account_id = Column(UUID, nullable=False)  # Creator account ID
    workflow_id = Column(UUID, nullable=False)  # Associated workflow ID
    graph = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )  # Runtime graph configuration
    state = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )  # Final workflow state
    latency = Column(
        Float,
        nullable=False,
        server_default=text("0.0"),
    )  # Total execution latency (seconds)
    status = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # Execution status
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
