#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : web_app_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField, BooleanField
from wtforms.validators import DataRequired, Optional, UUID

from internal.lib.helper import datetime_to_timestamp
from internal.model import App, Conversation


class GetWebAppResp(Schema):
    """Response structure for retrieving basic WebApp information."""
    id = fields.UUID(dump_default="")
    icon = fields.String(dump_default="")
    name = fields.String(dump_default="")
    description = fields.String(dump_default="")
    app_config = fields.Dict(dump_default={})

    @pre_dump
    def process_data(self, data: App, **kwargs):
        app_config = data.app_config
        return {
            "id": data.id,
            "icon": data.icon,
            "name": data.name,
            "description": data.description,
            "app_config": {
                "opening_statement": app_config.opening_statement,
                "opening_questions": app_config.opening_questions,
                "suggested_after_answer": app_config.suggested_after_answer,
            }
        }


class WebAppChatReq(FlaskForm):
    """Request structure for chatting with a WebApp."""
    conversation_id = StringField(
        "conversation_id",
        default="",
        validators=[
            Optional(),
            UUID(message="conversation_id must be a valid UUID")
        ]
    )
    query = StringField(
        "query",
        default="",
        validators=[
            DataRequired(message="query cannot be empty")
        ]
    )


class GetConversationsReq(FlaskForm):
    """Request structure for retrieving the WebApp conversation list."""
    is_pinned = BooleanField("is_pinned", default=False)


class GetConversationsResp(Schema):
    """Response structure for returning the WebApp conversation list."""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    summary = fields.String(dump_default="")
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Conversation, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "summary": data.summary,
            "created_at": datetime_to_timestamp(data.created_at),
        }
