#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : conversation.py
"""
from datetime import datetime

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
    func,
    PrimaryKeyConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from internal.extension.database_extension import db


class Conversation(db.Model):
    """Conversation model"""
    __tablename__ = "conversation"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_conversation_id"),
        Index("conversation_app_id_idx", "app_id"),
        Index("conversation_app_created_by_idx", "created_by"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    app_id = Column(UUID, nullable=False)  # Associated app ID
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Conversation name
    summary = Column(Text, nullable=False, server_default=text("''::text"))  # Conversation summary / long-term memory
    is_pinned = Column(Boolean, nullable=False, server_default=text("false"))  # Whether pinned
    is_deleted = Column(Boolean, nullable=False, server_default=text("false"))  # Soft delete flag
    invoke_from = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Invocation source
    created_by = Column(
        UUID,
        nullable=True,
    )  # Creator identifier: differs by invoke_from (web_app/debugger -> account ID; service_api -> end-user ID)
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=datetime.now,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))

    @property
    def is_new(self) -> bool:
        """Read-only property: whether this conversation is newly created."""
        message_count = db.session.query(func.count(Message.id)).filter(
            Message.conversation_id == self.id,
        ).scalar()

        return False if message_count > 1 else True


class Message(db.Model):
    """Message model"""
    __tablename__ = "message"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_message_id"),
        Index("message_conversation_id_idx", "conversation_id"),
        Index("message_created_by_idx", "created_by"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))

    # Message association fields
    app_id = Column(UUID, nullable=False)  # Associated app ID
    conversation_id = Column(UUID, nullable=False)  # Associated conversation ID
    invoke_from = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # Invocation source: service_api, web_app, debugger, etc.
    created_by = Column(UUID, nullable=False)  # Message creator: can be an LLMOps user or an end-user via OpenAPI

    # Original user query
    query = Column(Text, nullable=False, server_default=text("''::text"))  # Raw user query
    message = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Messages used to generate the answer
    message_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Total tokens in message list
    message_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Unit price for messages
    message_price_unit = Column(Numeric(10, 4), nullable=False, server_default=text("0.0"))  # Price unit

    # Generated answer
    answer = Column(Text, nullable=False, server_default=text("''::text"))  # Agent-generated answer
    answer_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Tokens for generated answer
    answer_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Unit price per token
    answer_price_unit = Column(Numeric(10, 4), nullable=False, server_default=text("0.0"))  # Price unit per token

    # Message-level statistics
    latency = Column(Float, nullable=False, server_default=text("0.0"))  # Total latency
    is_deleted = Column(Boolean, nullable=False, server_default=text("false"))  # Soft delete flag
    status = Column(String(255), nullable=False,
                    server_default=text("''::character varying"))  # Status: normal/error/stop
    error = Column(Text, nullable=False, server_default=text("''::text"))  # Error message (if any)
    total_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Total tokens consumed (all steps)
    total_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Total price (all steps)

    # Timestamps
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=datetime.now,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))

    # Agent thought steps (relationship)
    agent_thoughts = relationship(
        "MessageAgentThought",
        backref="msg",
        lazy="selectin",
        passive_deletes="all",
        uselist=True,
        foreign_keys=[id],
        primaryjoin="MessageAgentThought.message_id == Message.id",
    )


class MessageAgentThought(db.Model):
    """Agent reasoning step model (records steps while generating the final answer)."""
    __tablename__ = "message_agent_thought"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_message_agent_thought_id"),
        Index("message_agent_thought_app_id_idx", "app_id"),
        Index("message_agent_thought_conversation_id_idx", "conversation_id"),
        Index("message_agent_thought_message_id_idx", "message_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))

    # Step association fields
    app_id = Column(UUID, nullable=False)  # Associated app ID
    conversation_id = Column(UUID, nullable=False)  # Associated conversation ID
    message_id = Column(UUID, nullable=False)  # Associated message ID
    invoke_from = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # Invocation source: service_api, web_app, debugger, etc.
    created_by = Column(UUID, nullable=False)  # Creator: LLMOps user or end-user via OpenAPI

    # Step position within the message
    position = Column(Integer, nullable=False, server_default=text("0"))  # Step index

    # Thought and observation
    event = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Event name
    thought = Column(Text, nullable=False, server_default=text("''::text"))  # Thought content (LLM-generated)
    observation = Column(Text, nullable=False, server_default=text("''::text"))  # Observation (tool/KB/non-LLM output)

    # Tool call info
    tool = Column(Text, nullable=False, server_default=text("''::text"))  # Tool name
    tool_input = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Tool input (empty dict if none)

    # Prompt messages used in this step
    message = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Prompt messages sent to the LLM
    message_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Tokens used for prompt
    message_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Unit price (CNY)
    message_price_unit = Column(
        Numeric(10, 4),
        nullable=False,
        server_default=text("0"),
    )  # Price unit: 1000 means price per 1000 tokens

    # LLM generated content
    answer = Column(Text, nullable=False, server_default=text("''::text"))  # Generated content (same as thought)
    answer_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Tokens for generated content
    answer_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Unit price (CNY)
    answer_price_unit = Column(
        Numeric(10, 4),
        nullable=False,
        server_default=text("0.0"),
    )  # Price unit: price per 1000 tokens

    # Step-level statistics
    total_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Total tokens
    total_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Total cost
    latency = Column(Float, nullable=False, server_default=text("0.0"))  # Step latency

    # Timestamps
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=datetime.now,
    )  # Updated time
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))  # Created time
