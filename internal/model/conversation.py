#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : conversation.py
"""
from sqlalchemy import (
    Column,
    UUID,
    String,
    Text,
    Integer,
    DateTime,
    Boolean,
    Numeric,
    Float,
    text,
    PrimaryKeyConstraint, func, asc,
)
from sqlalchemy.dialects.postgresql import JSONB

from internal.extension.database_extension import db


class Conversation(db.Model):
    """Conversation Model"""
    __tablename__ = "conversation"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_conversation_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    app_id = Column(UUID, nullable=False)  # Associated application ID
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Conversation name
    summary = Column(Text, nullable=False, server_default=text("''::text"))  # Conversation summary / long-term memory
    is_pinned = Column(Boolean, nullable=False, server_default=text("false"))  # Whether pinned
    is_deleted = Column(Boolean, nullable=False, server_default=text("false"))  # Soft delete flag
    invoke_from = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Invocation source
    created_by = Column(
        UUID,
        nullable=True,
    )  # Conversation creator. Based on invoke_from: web_app/debugger -> account ID; service_api -> end user ID
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)'),
    )
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))

    @property
    def is_new(self) -> bool:
        """Read-only property: check whether the conversation is newly created."""
        message_count = db.session.query(func.count(Message.id)).filter(
            Message.conversation_id == self.id,
        ).scalar()

        return False if message_count > 1 else True


class Message(db.Model):
    """Message Model"""
    __tablename__ = "message"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_message_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))

    # Message-level references
    app_id = Column(UUID, nullable=False)  # Associated application ID
    conversation_id = Column(UUID, nullable=False)  # Associated conversation ID
    invoke_from = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # Invocation source: service_api, web_app, debugger, etc.
    created_by = Column(UUID, nullable=False)  # Creator of the message (LLMOps user or open-API end user)

    # Original user query
    query = Column(Text, nullable=False, server_default=text("''::text"))  # Original query from user
    message = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Message list that produced the answer
    message_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Token count of message list
    message_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Unit price for messages
    message_price_unit = Column(Numeric(10, 4), nullable=False, server_default=text("0.0"))  # Price unit

    # Answer information
    answer = Column(Text, nullable=False, server_default=text("''::text"))  # Agent-generated answer
    answer_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Token count for answer
    answer_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Unit price for tokens
    answer_price_unit = Column(Numeric(10, 4), nullable=False, server_default=text("0.0"))  # Price unit

    # Metrics
    latency = Column(Float, nullable=False, server_default=text("0.0"))  # Total latency for the message
    is_deleted = Column(Boolean, nullable=False, server_default=text("false"))  # Soft delete flag
    status = Column(String(255), nullable=False,
                    server_default=text("''::character varying"))  # Status: normal/error/stopped
    error = Column(Text, nullable=False, server_default=text("''::text"))  # Error information if occurred
    total_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Total token usage
    total_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Total price

    # Time info
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)'),
    )
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))

    @property
    def agent_thoughts(self) -> list["MessageAgentThought"]:
        """Read-only property: return the ordered list of the agent's reasoning steps."""
        return db.session.query(MessageAgentThought).filter(
            MessageAgentThought.message_id == self.id,
        ).order_by(asc("position")).all()


class MessageAgentThought(db.Model):
    """Agent Reasoning Model: stores intermediate reasoning steps during answer generation"""
    __tablename__ = "message_agent_thought"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_message_agent_thought_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))

    # Associations
    app_id = Column(UUID, nullable=False)  # Associated application ID
    conversation_id = Column(UUID, nullable=False)  # Associated conversation ID
    message_id = Column(UUID, nullable=False)  # Associated message ID
    invoke_from = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # Invocation source: service_api, web_app, debugger
    created_by = Column(UUID, nullable=False)  # Creator (LLMOps user or API end user)

    # Step position
    position = Column(Integer, nullable=False, server_default=text("0"))  # Step index in reasoning process

    # Reasoning and observation
    event = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Event name
    thought = Column(Text, nullable=False, server_default=text("''::text"))  # LLM-generated reasoning content
    observation = Column(Text, nullable=False,
                         server_default=text("''::text"))  # Observations (non-LLM content: KB/tool output)

    # Tool usage
    tool = Column(Text, nullable=False, server_default=text("''::text"))  # Tool name
    tool_input = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Tool input JSON

    # Prompt messages used in this step
    message = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Prompt messages sent to LLM
    message_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Token cost of prompts
    message_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Token unit price
    message_price_unit = Column(
        Numeric(10, 4),
        nullable=False,
        server_default=text("0"),
    )  # Price unit (1000 = per 1000 tokens)

    # LLM output content
    answer = Column(Text, nullable=False, server_default=text("''::text"))  # LLM-generated answer (same as thought)
    answer_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Token cost for answer
    answer_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))
    answer_price_unit = Column(
        Numeric(10, 4),
        nullable=False,
        server_default=text("0.0"),
    )

    # Aggregated statistics
    total_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Total token consumption
    total_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Total cost
    latency = Column(Float, nullable=False, server_default=text("0.0"))  # Step latency

    # Time info
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)'),
    )  # Update time
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))  # Creation time
