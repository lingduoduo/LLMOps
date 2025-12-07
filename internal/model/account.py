#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : account.py
"""
from flask import current_app
from flask_login import UserMixin
from sqlalchemy import (
    Column,
    UUID,
    String,
    DateTime,
    text,
    PrimaryKeyConstraint,
)

from internal.extension.database_extension import db
from .conversation import Conversation
from ..entity.conversation_entity import InvokeFrom


class Account(UserMixin, db.Model):
    """Account model"""
    __tablename__ = "account"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_account_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))
    email = Column(String(255), nullable=False, server_default=text("''::character varying"))
    avatar = Column(String(255), nullable=False, server_default=text("''::character varying"))
    password = Column(String(255), nullable=True, server_default=text("''::character varying"))
    password_salt = Column(String(255), nullable=True, server_default=text("''::character varying"))
    assistant_agent_conversation_id = Column(UUID, nullable=True)  # Assistant Agent conversation ID
    last_login_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))
    last_login_ip = Column(String(255), nullable=False, server_default=text("''::character varying"))
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))

    @property
    def is_password_set(self) -> bool:
        """Read-only property: whether the current account has a password set"""
        return self.password is not None and self.password != ""

    @property
    def assistant_agent_conversation(self) -> "Conversation":
        """Read-only property: returns the Assistant Agent conversation for this account"""
        # 1. Retrieve Assistant Agent application ID
        assistant_agent_id = current_app.config.get("ASSISTANT_AGENT_ID")
        conversation = db.session.query(Conversation).get(
            self.assistant_agent_conversation_id
        ) if self.assistant_agent_conversation_id else None

        # 2. If the conversation does not exist, create a new one
        if not self.assistant_agent_conversation_id or not conversation:
            # 3. Enter auto-commit context
            with db.auto_commit():
                # 4. Create a new Assistant Agent conversation
                conversation = Conversation(
                    app_id=assistant_agent_id,
                    name="New Conversation",
                    invoke_from=InvokeFrom.ASSISTANT_AGENT,
                    created_by=self.id,
                )
                db.session.add(conversation)
                db.session.flush()

                # 5. Update the Assistant Agent conversation ID for this account
                self.assistant_agent_conversation_id = conversation.id

        return conversation


class AccountOAuth(db.Model):
    """Account and third-party OAuth authorization record table"""
    __tablename__ = "account_oauth"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_account_oauth_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    account_id = Column(UUID, nullable=False)
    provider = Column(String(255), nullable=False, server_default=text("''::character varying"))
    openid = Column(String(255), nullable=False, server_default=text("''::character varying"))
    encrypted_token = Column(String(255), nullable=False, server_default=text("''::character varying"))
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))
