#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : app_schema.py
"""
from uuid import UUID

from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField, IntegerField
from wtforms.validators import DataRequired, Length, URL, ValidationError, Optional, NumberRange

from internal.lib.helper import datetime_to_timestamp
from internal.model import App, AppConfigVersion, Message
from pkg.paginator import PaginatorReq


class CreateAppReq(FlaskForm):
    """Request schema for creating an Agent application"""
    name = StringField(
        "name",
        validators=[
            DataRequired("Application name must not be empty"),
            Length(max=40, message="Application name cannot exceed 40 characters"),
        ],
    )
    icon = StringField(
        "icon",
        validators=[
            DataRequired("Application icon must not be empty"),
            URL(message="Application icon must be a valid image URL"),
        ],
    )
    description = StringField(
        "description",
        validators=[
            Length(max=800, message="Application description cannot exceed 800 characters"),
        ],
    )


class GetAppResp(Schema):
    """Response schema for retrieving basic application information"""
    id = fields.UUID(dump_default="")
    debug_conversation_id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    status = fields.String(dump_default="")
    draft_updated_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: App, **kwargs):
        return {
            "id": data.id,
            "debug_conversation_id": data.debug_conversation_id if data.debug_conversation_id else "",
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "status": data.status,
            "draft_updated_at": datetime_to_timestamp(data.draft_app_config.updated_at),
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }


class GetPublishHistoriesWithPageReq(PaginatorReq):
    """Request schema for paginated retrieval of application publish history"""
    pass


class GetPublishHistoriesWithPageResp(Schema):
    """Response schema for paginated list of application publish history"""
    id = fields.UUID(dump_default="")
    version = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: AppConfigVersion, **kwargs):
        return {
            "id": data.id,
            "version": data.version,
            "created_at": datetime_to_timestamp(data.created_at),
        }


class FallbackHistoryToDraftReq(FlaskForm):
    """Request schema for reverting a historical configuration version back to draft"""
    app_config_version_id = StringField(
        "app_config_version_id",
        validators=[
            DataRequired("Configuration version ID to revert must not be empty"),
        ],
    )

    def validate_app_config_version_id(self, field: StringField) -> None:
        """Validate that the configuration version ID is a valid UUID"""
        try:
            UUID(field.data)
        except Exception:
            raise ValidationError("Configuration version ID must be a valid UUID")


class UpdateDebugConversationSummaryReq(FlaskForm):
    """Request schema for updating the long-term memory summary of a debug conversation"""
    summary = StringField("summary", default="")


class DebugChatReq(FlaskForm):
    """Request schema for starting a debug chat session"""
    query = StringField(
        "query",
        validators=[
            DataRequired("User query must not be empty"),
        ],
    )


class GetDebugConversationMessagesWithPageReq(PaginatorReq):
    """Request schema for paginated retrieval of debug conversation messages"""
    created_at = IntegerField(
        "created_at",
        default=0,
        validators=[
            Optional(),
            NumberRange(min=0, message="The minimum value for created_at cursor is 0"),
        ],
    )


class GetDebugConversationMessagesWithPageResp(Schema):
    """Response schema for paginated list of debug conversation messages"""
    id = fields.UUID(dump_default="")
    conversation_id = fields.UUID(dump_default="")
    query = fields.String(dump_default="")
    answer = fields.String(dump_default="")
    total_token_count = fields.Integer(dump_default=0)
    latency = fields.Float(dump_default=0)
    agent_thoughts = fields.List(fields.Dict, dump_default=[])
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Message, **kwargs):
        return {
            "id": data.id,
            "conversation_id": data.conversation_id,
            "query": data.query,
            "answer": data.answer,
            "total_token_count": data.total_token_count,
            "latency": data.latency,
            "agent_thoughts": [
                {
                    "id": agent_thought.id,
                    "position": agent_thought.position,
                    "event": agent_thought.event,
                    "thought": agent_thought.thought,
                    "observation": agent_thought.observation,
                    "tool": agent_thought.tool,
                    "tool_input": agent_thought.tool_input,
                    "latency": agent_thought.latency,
                    "created_at": datetime_to_timestamp(agent_thought.created_at),
                }
                for agent_thought in data.agent_thoughts
            ],
            "created_at": datetime_to_timestamp(data.created_at),
        }
