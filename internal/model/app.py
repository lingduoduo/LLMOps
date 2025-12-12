#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : app.py
"""
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

from internal.entity.app_entity import AppConfigType, DEFAULT_APP_CONFIG, AppStatus
from internal.entity.conversation_entity import InvokeFrom
from internal.extension.database_extension import db
from .conversation import Conversation
from ..lib.helper import generate_random_string


class App(db.Model):
    """Base model class for AI applications"""
    __tablename__ = "app"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    account_id = Column(UUID, nullable=False)  # ID of the account that created this app
    app_config_id = Column(UUID, nullable=True)  # Published config ID; None means not published
    draft_app_config_id = Column(UUID, nullable=True)  # Associated draft config ID
    debug_conversation_id = Column(UUID, nullable=True)  # Debug conversation ID; None means no conversation yet
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))  # App name
    icon = Column(String(255), nullable=False, server_default=text("''::character varying"))  # App icon
    description = Column(Text, nullable=False, server_default=text("''::text"))  # App description
    token = Column(String(255), nullable=True, server_default=text("''::character varying"))
    status = Column(String(255), nullable=False, server_default=text("''::character varying"))  # App status
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))

    @property
    def app_config(self) -> "AppConfig":
        """Read-only property that returns the current runtime config of the app"""
        if not self.app_config_id:
            return None
        return db.session.query(AppConfig).get(self.app_config_id)

    @property
    def draft_app_config(self) -> "AppConfigVersion":
        """Read-only property that returns the current draft config of the app"""
        # 1. Fetch the current draft config for this app
        app_config_version = db.session.query(AppConfigVersion).filter(
            AppConfigVersion.app_id == self.id,
            AppConfigVersion.config_type == AppConfigType.DRAFT,
        ).one_or_none()

        # 2. If it does not exist, create a default draft config
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
        """Get the debug conversation record for this app"""
        # 1. Get the debug conversation record based on debug_conversation_id
        debug_conversation = None
        if self.debug_conversation_id is not None:
            debug_conversation = db.session.query(Conversation).filter(
                Conversation.id == self.debug_conversation_id,
                Conversation.invoke_from == InvokeFrom.DEBUGGER,
            ).one_or_none()

        # 2. If it does not exist, create a new one
        if not self.debug_conversation_id or not debug_conversation:
            # 3. Enter an auto-commit context
            with db.auto_commit():
                # 4. Create a new debug conversation record and flush to get its ID
                debug_conversation = Conversation(
                    app_id=self.id,
                    name="New Conversation",
                    invoke_from=InvokeFrom.DEBUGGER,
                    created_by=self.account_id,
                )
                db.session.add(debug_conversation)
                db.session.flush()

                # 5. Update the debug_conversation_id for the current app record
                self.debug_conversation_id = debug_conversation.id

        return debug_conversation

    @property
    def token_with_default(self) -> str:
        """Get the token with a default value if needed."""
        # 1. Check whether the status is PUBLISHED
        if self.status != AppStatus.PUBLISHED:
            # 2. If not published, clear the token and commit the update
            if self.token is not None or self.token != "":
                self.token = None
                db.session.commit()
            return ""

        # 3. If published, check whether the token exists; if not, generate one
        if self.token is None or self.token == "":
            self.token = generate_random_string(16)
            db.session.commit()

        return self.token


class AppConfig(db.Model):
    """Application configuration model"""
    __tablename__ = "app_config"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_config_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # Config ID
    app_id = Column(UUID, nullable=False)  # Associated app ID
    model_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Model configuration
    dialog_round = Column(Integer, nullable=False,
                          server_default=text("0"))  # Number of dialogue context rounds to retain
    preset_prompt = Column(Text, nullable=False, server_default=text("''::text"))  # Preset prompt
    tools = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # List of tools associated with the app
    workflows = Column(JSONB, nullable=False,
                       server_default=text("'[]'::jsonb"))  # List of workflows associated with the app
    retrieval_config = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Retrieval configuration
    long_term_memory = Column(JSONB, nullable=False,
                              server_default=text("'{}'::jsonb"))  # Long-term memory configuration
    opening_statement = Column(Text, nullable=False, server_default=text("''::text"))  # Opening statement text
    opening_questions = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Suggested opening questions
    speech_to_text = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Speech-to-text configuration
    text_to_speech = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Text-to-speech configuration
    suggested_after_answer = Column(
        JSONB,
        nullable=False,
        server_default=text("'{\"enable\": true}'::jsonb"),
    )  # Generate suggested questions after answering
    review_config = Column(JSONB, nullable=False,
                           server_default=text("'{}'::jsonb"))  # Review / moderation configuration
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))

    @property
    def app_dataset_joins(self) -> list["AppDatasetJoin"]:
        """Read-only property that returns the knowledge base association records for this config"""
        return (
            db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == self.app_id
            ).all()
        )


class AppConfigVersion(db.Model):
    """Application config version history table, storing draft and published configs"""
    __tablename__ = "app_config_version"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_config_version_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # Config ID
    app_id = Column(UUID, nullable=False)  # Associated app ID
    model_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Model configuration
    dialog_round = Column(Integer, nullable=False,
                          server_default=text("0"))  # Number of dialogue context rounds to retain
    preset_prompt = Column(Text, nullable=False, server_default=text("''::text"))  # Persona and reply logic
    tools = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # List of tools associated with the app
    workflows = Column(JSONB, nullable=False,
                       server_default=text("'[]'::jsonb"))  # List of workflows associated with the app
    datasets = Column(JSONB, nullable=False,
                      server_default=text("'[]'::jsonb"))  # List of knowledge bases associated with the app
    retrieval_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Retrieval configuration
    long_term_memory = Column(JSONB, nullable=False,
                              server_default=text("'{}'::jsonb"))  # Long-term memory configuration
    opening_statement = Column(Text, nullable=False, server_default=text("''::text"))  # Opening statement text
    opening_questions = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # Suggested opening questions
    speech_to_text = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Speech-to-text configuration
    text_to_speech = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # Text-to-speech configuration
    suggested_after_answer = Column(
        JSONB,
        nullable=False,
        server_default=text("'{\"enable\": true}'::jsonb"),
    )  # Generate suggested questions after answering
    review_config = Column(JSONB, nullable=False,
                           server_default=text("'{}'::jsonb"))  # Review / moderation configuration
    version = Column(Integer, nullable=False, server_default=text("0"))  # Published version number
    config_type = Column(String(255), nullable=False, server_default=text("''::character varying"))  # Config type
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))


class AppDatasetJoin(db.Model):
    """Model for app–knowledge-base association records"""
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
