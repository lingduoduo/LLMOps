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
    PrimaryKeyConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from internal.extension.database_extension import db


class Conversation(db.Model):
    """Conversation model representing a chat session."""
    __tablename__ = "conversation"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_conversation_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    app_id = Column(UUID, nullable=False)  # Associated application ID
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Conversation name
    summary = Column(Text, nullable=False, server_default=text("''::text"))  # Conversation summary / long-term memory
    is_pinned = Column(Boolean, nullable=False, server_default=text("false"))  # Whether the conversation is pinned
    is_deleted = Column(Boolean, nullable=False, server_default=text("false"))  # Whether the conversation is deleted
    invoke_from = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Invocation source
    created_by = Column(
        UUID,
        nullable=True,
    )  # Creator of the conversation; may vary by invocation source. For example, `web_app` and `debugger` record account IDs, while `service_api` records end-user IDs.
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)'),
    )
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))


class Message(db.Model):
    """Message model representing individual chat messages."""
    __tablename__ = "message"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_message_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))

    # Message association fields
    app_id = Column(UUID, nullable=False)  # Associated application ID
    conversation_id = Column(UUID, nullable=False)  # Associated conversation ID
    invoke_from = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # Invocation source, e.g., service_api, web_app, debugger
    created_by = Column(UUID, nullable=False)  # Creator of the message (LLMOps user or API end user)

    # User query and message data
    query = Column(Text, nullable=False, server_default=text("''::text"))  # Original user query
    message = Column(JSONB, nullable=False,
                     server_default=text("'[]'::jsonb"))  # List of messages that produced the answer
    message_token_count = Column(Integer, nullable=False,
                                 server_default=text("0"))  # Total token count for the message list
    message_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Unit price per token
    message_price_unit = Column(Numeric(10, 4), nullable=False, server_default=text("0.0"))  # Price unit

    # Agent-generated answer data
    answer = Column(Text, nullable=False, server_default=text("''::text"))  # Agent-generated answer
    answer_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Token count for the answer
    answer_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Unit price per token
    answer_price_unit = Column(Numeric(10, 4), nullable=False, server_default=text("0.0"))  # Price unit

    # Performance and status tracking
    latency = Column(Float, nullable=False, server_default=text("0.0"))  # Total message latency
    is_deleted = Column(Boolean, nullable=False, server_default=text("false"))  # Soft delete flag
    status = Column(String(255), nullable=False,
                    server_default=text("''::character varying"))  # Message status (normal, error, stopped)
    error = Column(Text, nullable=False, server_default=text("''::text"))  # Error message if any
    total_token_count = Column(Integer, nullable=False,
                               server_default=text("0"))  # Total tokens consumed (including intermediate steps)
    total_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Total price consumed

    # Time tracking
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)'),
    )
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))


class MessageAgentThought(db.Model):
    """Agent reasoning model for recording LLM reasoning and observations during answer generation."""
    __tablename__ = "message_agent_thought"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_message_agent_thought_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))

    # Linking and metadata
    app_id = Column(UUID, nullable=False)  # Associated application ID
    conversation_id = Column(UUID, nullable=False)  # Associated conversation ID
    message_id = Column(UUID, nullable=False)  # Associated message ID
    invoke_from = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # Invocation source (e.g., service_api, web_app, debugger)
    created_by = Column(UUID, nullable=False)  # Creator (LLMOps user or end user)

    # Execution position within the message
    position = Column(Integer, nullable=False, server_default=text("0"))  # Position of the reasoning/observation step

    # Reasoning and observation (LLM and non-LLM content)
    event = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Event name
    thought = Column(Text, nullable=False, server_default=text("''::text"))  # LLM-generated reasoning content
    observation = Column(Text, nullable=False,
                         server_default=text("''::text"))  # Observation content (from tools, KB, etc.)

    # Tool invocation details
    tool = Column(Text, nullable=False, server_default=text("''::text"))  # Tool name invoked by the agent
    tool_input = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Input to the tool (if any)

    # Prompt messages used during the reasoning step
    message = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Prompt messages sent to the LLM
    message_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Tokens used in messages
    message_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Token unit price (in CNY)
    message_price_unit = Column(
        Numeric(10, 4),
        nullable=False,
        server_default=text("0"),
    )  # Price unit (e.g., per 1000 tokens)

    # LLM-generated content details
    answer = Column(Text, nullable=False, server_default=text("''::text"))  # LLM-generated output (same as thought)
    answer_token_count = Column(Integer, nullable=False,
                                server_default=text("0"))  # Tokens consumed to generate the answer
    answer_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Token unit price (in CNY)
    answer_price_unit = Column(
        Numeric(10, 4),
        nullable=False,
        server_default=text("0.0"),
    )  # Price unit (per 1000 tokens)

    # Aggregated statistics
    total_token_count = Column(Integer, nullable=False, server_default=text("0"))  # Total tokens consumed
    total_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # Total cost
    latency = Column(Float, nullable=False, server_default=text("0.0"))  # Latency for this reasoning/observation step

    # Timestamps
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)'),
    )  # Last update time
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))  # Creation time
