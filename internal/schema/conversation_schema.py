#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : conversation_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import IntegerField, StringField, BooleanField
from wtforms.validators import Optional, NumberRange, DataRequired, Length

from internal.lib.helper import datetime_to_timestamp
from internal.model import Message
from pkg.paginator import PaginatorReq


class GetConversationMessagesWithPageReq(PaginatorReq):
    """Request schema for paginated retrieval of messages in a specific conversation"""
    created_at = IntegerField(
        "created_at",
        default=0,
        validators=[
            Optional(),
            NumberRange(min=0, message="The minimum value for the created_at cursor is 0")
        ]
    )


class GetConversationMessagesWithPageResp(Schema):
    """Response schema for paginated retrieval of messages in a specific conversation"""
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


class UpdateConversationNameReq(FlaskForm):
    """Request schema for updating a conversation name"""
    name = StringField(
        "name",
        validators=[
            DataRequired(message="Conversation name cannot be empty"),
            Length(max=100, message="Conversation name cannot exceed 100 characters")
        ]
    )


class UpdateConversationIsPinnedReq(FlaskForm):
    """Request schema for updating the pinned status of a conversation"""
    is_pinned = BooleanField("is_pinned", default=False)
