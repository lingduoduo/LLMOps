#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : workflow_schema.py
"""
from flask_wtf import FlaskForm
from internal.entity.workflow_entity import WorkflowStatus
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField
from wtforms.validators import DataRequired, Length, Regexp, URL, Optional, AnyOf

from internal.core.workflow.entities.workflow_entity import WORKFLOW_CONFIG_NAME_PATTERN
from internal.lib.helper import datetime_to_timestamp
from internal.model import Workflow
from pkg.paginator import PaginatorReq


class CreateWorkflowReq(FlaskForm):
    """Create workflow base request"""
    name = StringField(
        "name",
        validators=[
            DataRequired("Workflow name cannot be empty"),
            Length(max=50, message="Workflow name cannot exceed 50 characters"),
        ],
    )
    tool_call_name = StringField(
        "tool_call_name",
        validators=[
            DataRequired("English name cannot be empty"),
            Length(max=50, message="English name cannot exceed 50 characters"),
            Regexp(
                WORKFLOW_CONFIG_NAME_PATTERN,
                message=(
                    "English name supports only letters, digits, and underscores, "
                    "and must start with a letter or underscore"
                ),
            ),
        ],
    )
    icon = StringField(
        "icon",
        validators=[
            DataRequired("Workflow icon cannot be empty"),
            URL(message="Workflow icon must be a valid image URL"),
        ],
    )
    description = StringField(
        "description",
        validators=[
            DataRequired("Workflow description cannot be empty"),
            Length(max=1024, message="Workflow description cannot exceed 1024 characters"),
        ],
    )


class UpdateWorkflowReq(FlaskForm):
    """Update workflow base request"""
    name = StringField(
        "name",
        validators=[
            DataRequired("Workflow name cannot be empty"),
            Length(max=50, message="Workflow name cannot exceed 50 characters"),
        ],
    )
    tool_call_name = StringField(
        "tool_call_name",
        validators=[
            DataRequired("English name cannot be empty"),
            Length(max=50, message="English name cannot exceed 50 characters"),
            Regexp(
                WORKFLOW_CONFIG_NAME_PATTERN,
                message=(
                    "English name supports only letters, digits, and underscores, "
                    "and must start with a letter or underscore"
                ),
            ),
        ],
    )
    icon = StringField(
        "icon",
        validators=[
            DataRequired("Workflow icon cannot be empty"),
            URL(message="Workflow icon must be a valid image URL"),
        ],
    )
    description = StringField(
        "description",
        validators=[
            DataRequired("Workflow description cannot be empty"),
            Length(max=1024, message="Workflow description cannot exceed 1024 characters"),
        ],
    )


class GetWorkflowResp(Schema):
    """Get workflow detail response structure"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    tool_call_name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    status = fields.String(dump_default="")
    is_debug_passed = fields.Boolean(dump_default=False)
    node_count = fields.Integer(dump_default=0)
    published_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Workflow, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "tool_call_name": data.tool_call_name,
            "icon": data.icon,
            "description": data.description,
            "status": data.status,
            "is_debug_passed": data.is_debug_passed,
            "node_count": len(data.draft_graph.get("nodes", [])),
            "published_at": datetime_to_timestamp(data.published_at),
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }


class GetWorkflowsWithPageReq(PaginatorReq):
    """Get paginated workflow list request structure"""
    status = StringField(
        "status",
        default="",
        validators=[
            Optional(),
            AnyOf(WorkflowStatus.__members__.values(), message="Invalid workflow status format"),
        ],
    )
    search_word = StringField(
        "search_word",
        default="",
        validators=[Optional()],
    )


class GetWorkflowsWithPageResp(Schema):
    """Get paginated workflow list response structure"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    tool_call_name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    status = fields.String(dump_default="")
    is_debug_passed = fields.Boolean(dump_default=False)
    node_count = fields.Integer(dump_default=0)
    published_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Workflow, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "tool_call_name": data.tool_call_name,
            "icon": data.icon,
            "description": data.description,
            "status": data.status,
            "is_debug_passed": data.is_debug_passed,
            "node_count": len(data.graph.get("nodes", [])),
            "published_at": datetime_to_timestamp(data.published_at),
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }
