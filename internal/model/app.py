#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : app.py
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    UUID,
    String,
    Text,
    Integer,
    DateTime,
    text,
    PrimaryKeyConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB

from internal.entity.app_entity import AppConfigType, DEFAULT_APP_CONFIG, AppStatus
from internal.entity.conversation_entity import InvokeFrom
from internal.extension.database_extension import db
from internal.lib.helper import generate_random_string
from .conversation import Conversation


class App(db.Model):
    """Base model for AI applications"""
    __tablename__ = "app"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_id"),
        Index("app_account_id_idx", "account_id"),
        Index("app_token_idx", "token"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    account_id = Column(UUID, nullable=False)  # Creator account ID
    app_config_id = Column(UUID, nullable=True)  # Published configuration ID; None means not published
    draft_app_config_id = Column(UUID, nullable=True)  # Associated draft configuration ID
    debug_conversation_id = Column(UUID, nullable=True)  # Debug conversation ID; None means no conversation
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))  # App name
    icon = Column(String(255), nullable=False, server_default=text("''::character varying"))  # App icon
    description = Column(Text, nullable=False, server_default=text("''::text"))  # App description
    token = Column(String(255), nullable=True, server_default=text("''::character varying"))  # App access token
    status = Column(String(255), nullable=False, server_default=text("''::character varying"))  # App status
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=datetime.now,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))

    @property
    def app_config(self) -> "AppConfig":
        """Read-only property: return the active (published) app configuration."""
        if not self.app_config_id:
            return None
        return db.session.query(AppConfig).get(self.app_config_id)

    @property
    def draft_app_config(self) -> "AppConfigVersion":
        """Read-only property: return the draft configuration for this app."""
        # 1. Retrieve the draft configuration
        app_config_version = db.session.query(AppConfigVersion).filter(
            AppConfigVersion.app_id == self.id,
            AppConfigVersion.config_type == AppConfigType.DRAFT,
        ).one_or_none()

        # 2. If it does not exist, create a default draft configuration
        if not app_config_version:
            app_config_version = AppConfigVersion(
                app_id=self.id,
                version=0,
                config_type=AppConfigType.DRAFT,
                **DEFAULT_APP_CONFIG,
            )
            db.session.add(app_config_version)
            db.session.commit()

        return app_config_version

    @property
    def debug_conversation(self) -> "Conversation":
        """Return the debug conversation for this app."""
        # 1. Retrieve the debug conversation by ID
        debug_conversation = None
        if self.debug_conversation_id is not None:
            debug_conversation = db.session.query(Conversation).filter(
                Conversation.id == self.debug_conversation_id,
                Conversation.invoke_from == InvokeFrom.DEBUGGER,
            ).one_or_none()

        # 2. If it does not exist, create a new one
        if not self.debug_conversation_id or not debug_conversation:
            with db.auto_commit():
                debug_conversation = Conversation(
                    app_id=self.id,
                    name="New Conversation",
                    invoke_from=InvokeFrom.DEBUGGER,
                    created_by=self.account_id,
                )
                db.session.add(debug_conversation)
                db.session.flush()

                # Update the debug conversation ID
                self.debug_conversation_id = debug_conversation.id

        return debug_conversation

    @property
    def token_with_default(self) -> str:
        """Return a valid app token, generating or clearing it based on app status."""
        # 1. If the app is not published, clear the token
        if self.status != AppStatus.PUBLISHED:
            if self.token is not None or self.token != "":
                self.token = None
                db.session.commit()
            return ""

        # 2. If published and token does not exist, generate one
        if self.token is None or self.token == "":
            self.token = generate_random_string(16)
            db.session.commit()

        return self.token


class AppConfig(db.Model):
    """Application configuration model"""
    __tablename__ = "app_config"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_config_id"),
        Index("app_config_app_id_idx", "app_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # Config ID
    app_id = Column(UUID, nullable=False)  # Associated app ID
    model_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Model configuration
    dialog_round = Column(Integer, nullable=False, server_default=text("0"))  # Context window size
    preset_prompt = Column(Text, nullable=False, server_default=text("''::text"))  # Preset prompt
    tools = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Associated tools
    workflows = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Associated workflows
    retrieval_config = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Retrieval configuration
    long_term_memory = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Long-term memory config
    opening_statement = Column(Text, nullable=False, server_default=text("''::text"))  # Opening message
    opening_questions = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Suggested opening questions
    speech_to_text = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Speech-to-text config
    text_to_speech = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Text-to-speech config
    suggested_after_answer = Column(
        JSONB,
        nullable=False,
        server_default=text("'{\"enable\": true}'::jsonb"),
    )  # Generate suggested questions after answers
    review_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Review configuration
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=datetime.now,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))

    @property
    def app_dataset_joins(self) -> list["AppDatasetJoin"]:
        """Read-only property: return dataset associations for this app."""
        return db.session.query(AppDatasetJoin).filter(
            AppDatasetJoin.app_id == self.app_id
        ).all()


class AppConfigVersion(db.Model):
    """Application configuration version history (drafts and published versions)."""
    __tablename__ = "app_config_version"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_config_version_id"),
        Index("app_config_version_app_id_idx", "app_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # Config ID
    app_id = Column(UUID, nullable=False)  # Associated app ID
    model_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Model configuration
    dialog_round = Column(Integer, nullable=False, server_default=text("0"))  # Context window size
    preset_prompt = Column(Text, nullable=False, server_default=text("''::text"))  # Persona & response logic
    tools = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Associated tools
    workflows = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Associated workflows
    datasets = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Associated datasets
    retrieval_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Retrieval configuration
    long_term_memory = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Long-term memory config
    opening_statement = Column(Text, nullable=False, server_default=text("''::text"))  # Opening message
    opening_questions = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Suggested opening questions
    speech_to_text = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Speech-to-text config
    text_to_speech = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Text-to-speech config
    suggested_after_answer = Column(
        JSONB,
        nullable=False,
        server_default=text("'{\"enable\": true}'::jsonb"),
    )  # Generate suggested questions after answers
    review_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Review configuration
    version = Column(Integer, nullable=False, server_default=text("0"))  # Version number
    config_type = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Config type
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=datetime.now,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))


class AppDatasetJoin(db.Model):
    """Application ↔ dataset association model"""
    __tablename__ = "app_dataset_join"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_dataset_join_id"),
        Index("app_dataset_join_app_id_dataset_id_idx", "app_id", "dataset_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    app_id = Column(UUID, nullable=False)
    dataset_id = Column(UUID, nullable=False)
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=datetime.now,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))
