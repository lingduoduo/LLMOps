#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : app.py
"""
from internal.entity.app_entity import AppConfigType, DEFAULT_APP_CONFIG
from sqlalchemy import (
    Column,
    UUID,
    String,
    Text,
    Integer,
    DateTime,
    PrimaryKeyConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from internal.entity.conversation_entity import InvokeFrom
from internal.extension.database_extension import db
from .conversation import Conversation


class App(db.Model):
    """Base model for AI applications"""
    __tablename__ = "app"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    account_id = Column(UUID, nullable=False)  # Creator account ID
    app_config_id = Column(UUID, nullable=True)  # Published configuration ID (None means not yet published)
    draft_app_config_id = Column(UUID, nullable=True)  # Associated draft configuration ID
    debug_conversation_id = Column(UUID, nullable=True)  # Debugging conversation ID (None means no record)
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))  # App name
    icon = Column(String(255), nullable=False, server_default=text("''::character varying"))  # App icon
    description = Column(Text, nullable=False, server_default=text("''::text"))  # App description
    status = Column(String(255), nullable=False, server_default=text("''::character varying"))  # App status
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))

    @property
    def draft_app_config(self) -> "AppConfigVersion":
        """Read-only property: return the current draft configuration for this app"""
        # 1. Retrieve the current draft configuration for the app
        app_config_version = db.session.query(AppConfigVersion).filter(
            AppConfigVersion.app_id == self.id,
            AppConfigVersion.config_type == AppConfigType.DRAFT,
        ).one_or_none()

        # 2. If no configuration exists, create a default one
        if not app_config_version:
            app_config_version = AppConfigVersion(
                app_id=self.id,
                version=0,
                config_type=AppConfigType.DRAFT,
                **DEFAULT_APP_CONFIG
            )
            db.session.add(app_config_version)
            db.session.commit()

        return app_config_version

    @property
    def debug_conversation(self) -> "Conversation":
        """Retrieve the app’s debugging conversation record"""
        # 1. Get the conversation record using debug_conversation_id
        debug_conversation = None
        if self.debug_conversation_id is not None:
            debug_conversation = db.session.query(Conversation).filter(
                Conversation.id == self.debug_conversation_id,
                Conversation.invoke_from == InvokeFrom.DEBUGGER,
            ).one_or_none()

        # 2. If not found, create a new conversation
        if not self.debug_conversation_id or not debug_conversation:
            # 3. Use an auto-commit context for DB operations
            with db.auto_commit():
                # 4. Create a new debug conversation and flush to get its ID
                debug_conversation = Conversation(
                    app_id=self.id,
                    name="New Conversation",
                    invoke_from=InvokeFrom.DEBUGGER,
                    created_by=self.account_id,
                )
                db.session.add(debug_conversation)
                db.session.flush()

                # 5. Update the current app’s debug_conversation_id
                self.debug_conversation_id = debug_conversation.id

        return debug_conversation


class AppConfig(db.Model):
    """App configuration model"""
    __tablename__ = "app_config"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_config_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # Configuration ID
    app_id = Column(UUID, nullable=False)  # Linked app ID
    model_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Model configuration
    dialog_round = Column(Integer, nullable=False, server_default=text("0"))  # Context round count
    preset_prompt = Column(Text, nullable=False, server_default=text("''::text"))  # Preset prompt
    tools = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Associated tools
    workflows = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Associated workflows
    retrieval_config = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Retrieval configuration
    long_term_memory = Column(JSONB, nullable=False,
                              server_default=text("'{}'::jsonb"))  # Long-term memory configuration
    opening_statement = Column(Text, nullable=False, server_default=text("''::text"))  # Opening statement
    opening_questions = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Suggested opening questions
    speech_to_text = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Speech-to-text configuration
    text_to_speech = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Text-to-speech configuration
    review_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Review configuration
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))


class AppConfigVersion(db.Model):
    """Versioned app configuration history — stores both draft and published versions"""
    __tablename__ = "app_config_version"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_config_version_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # Configuration ID
    app_id = Column(UUID, nullable=False)  # Linked app ID
    model_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Model configuration
    dialog_round = Column(Integer, nullable=False, server_default=text("0"))  # Context round count
    preset_prompt = Column(Text, nullable=False, server_default=text("''::text"))  # Character setup and response logic
    tools = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Associated tools
    workflows = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Associated workflows
    datasets = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Associated knowledge base datasets
    retrieval_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Retrieval configuration
    long_term_memory = Column(JSONB, nullable=False,
                              server_default=text("'{}'::jsonb"))  # Long-term memory configuration
    opening_statement = Column(Text, nullable=False, server_default=text("''::text"))  # Opening statement
    opening_questions = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Suggested opening questions
    speech_to_text = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Speech-to-text configuration
    text_to_speech = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Text-to-speech configuration
    review_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Review configuration
    version = Column(Integer, nullable=False, server_default=text("0"))  # Version number
    config_type = Column(String(255), nullable=False,
                         server_default=text("''::character varying"))  # Configuration type
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))


class AppDatasetJoin(db.Model):
    """Association table linking apps with their datasets"""
    __tablename__ = "app_dataset_join"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_dataset_join_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    app_id = Column(UUID, nullable=False)
    dataset_id = Column(UUID, nullable=False)
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))
