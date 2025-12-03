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

from internal.entity.app_entity import AppStatus
from internal.lib.helper import datetime_to_timestamp
from internal.model import App, AppConfigVersion, Message
from pkg.paginator import PaginatorReq


class CreateAppReq(FlaskForm):
    """Request schema for creating an Agent application"""
    name = StringField("name", validators=[
        DataRequired("Application name cannot be empty"),
        Length(max=40, message="Application name cannot exceed 40 characters"),
    ])
    icon = StringField("icon", validators=[
        DataRequired("Application icon cannot be empty"),
        URL(message="Application icon must be a valid image URL"),
    ])
    description = StringField("description", validators=[
        Length(max=800, message="Application description cannot exceed 800 characters")
    ])


class UpdateAppReq(FlaskForm):
    """Request schema for updating an Agent application"""
    name = StringField("name", validators=[
        DataRequired("Application name cannot be empty"),
        Length(max=40, message="Application name cannot exceed 40 characters"),
    ])
    icon = StringField("icon", validators=[
        DataRequired("Application icon cannot be empty"),
        URL(message="Application icon must be a valid image URL"),
    ])
    description = StringField("description", validators=[
        Length(max=800, message="Application description cannot exceed 800 characters")
    ])


class GetAppsWithPageReq(PaginatorReq):
    """Request schema for paginated application list"""
    search_word = StringField("search_word", default="", validators=[Optional()])


class GetAppsWithPageResp(Schema):
    """Response schema for paginated application list"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    preset_prompt = fields.String(dump_default="")
    model_config = fields.Dict(dump_default={})
    status = fields.String(dump_default="")
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: App, **kwargs):
        app_config = data.app_config if data.status == AppStatus.PUBLISHED else data.draft_app_config
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "preset_prompt": app_config.preset_prompt,
            "model_config": {
                "provider": app_config.model_config.get("provider", ""),
                "model": app_config.model_config.get("model", "")
            },
            "status": data.status,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }


class GetAppResp(Schema):
    """Response schema for basic application info"""
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
    """Request schema for paginated publish history list"""
    ...


class GetPublishHistoriesWithPageResp(Schema):
    """Response schema for paginated publish history list"""
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
    """Request schema for reverting a history version back to draft"""
    app_config_version_id = StringField("app_config_version_id", validators=[
        DataRequired("Configuration version ID cannot be empty")
    ])

    def validate_app_config_version_id(self, field: StringField) -> None:
        """Validate the configuration version ID"""
        try:
            UUID(field.data)
        except Exception:
            raise ValidationError("Configuration version ID must be a valid UUID")


class UpdateDebugConversationSummaryReq(FlaskForm):
    """Request schema for updating long-term memory summary"""
    summary = StringField("summary", default="")


class DebugChatReq(FlaskForm):
    """Request schema for debug chat"""
    query = StringField("query", validators=[
        DataRequired("User query cannot be empty"),
    ])


class GetDebugConversationMessagesWithPageReq(PaginatorReq):
    """Request schema for paginated debug conversation messages"""
    created_at = IntegerField("created_at", default=0, validators=[
        Optional(),
        NumberRange(min=0, message="created_at cursor minimum value is 0")
    ])


class GetDebugConversationMessagesWithPageResp(Schema):
    """Response schema for paginated debug conversation messages"""
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
            "agent_thoughts": [{
                "id": agent_thought.id,
                "position": agent_thought.position,
                "event": agent_thought.event,
                "thought": agent_thought.thought,
                "observation": agent_thought.observation,
                "tool": agent_thought.tool,
                "tool_input": agent_thought.tool_input,
                "latency": agent_thought.latency,
                "created_at": datetime_to_timestamp(agent_thought.created_at),
            } for agent_thought in data.agent_thoughts],
            "created_at": datetime_to_timestamp(data.created_at),
        }
