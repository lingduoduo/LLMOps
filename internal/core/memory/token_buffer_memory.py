#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : token_buffer_memory.py
"""
from dataclasses import dataclass

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage, trim_messages, get_buffer_string
from sqlalchemy import desc

from internal.entity.conversation_entity import MessageStatus
from internal.model import Conversation, Message
from pkg.sqlalchemy import SQLAlchemy


@dataclass
class TokenBufferMemory:
    """Token-based buffer memory component"""
    db: SQLAlchemy  # Database instance
    conversation: Conversation  # Conversation model
    model_instance: BaseLanguageModel  # LLM instance

    def get_history_prompt_messages(
            self,
            max_token_limit: int = 2000,
            message_limit: int = 10,
    ) -> list[AnyMessage]:
        """Retrieve conversation history messages based on token + message count limits"""
        # 1. Check whether the conversation exists; if not, return empty list
        if self.conversation is None:
            return []

        # 2. Query messages for this conversation:
        #    ordered by time DESC, answer not empty,
        #    not soft deleted, and status is NORMAL or STOP
        messages = self.db.session.query(Message).filter(
            Message.conversation_id == self.conversation.id,
            Message.answer != "",
            Message.is_deleted == False,
            Message.status.in_([MessageStatus.NORMAL, MessageStatus.STOP]),
        ).order_by(desc("created_at")).limit(message_limit).all()
        messages = list(reversed(messages))

        # 3. Convert message ORM objects into LangChain message list
        prompt_messages = []
        for message in messages:
            prompt_messages.extend([
                HumanMessage(content=message.query),
                AIMessage(content=message.answer),
            ])

        # 4. Use LangChain's trim_messages to trim history by token limit
        return trim_messages(
            messages=prompt_messages,
            max_tokens=max_token_limit,
            token_counter=self.model_instance,
            strategy="last",
        )

    def get_history_prompt_text(
            self,
            human_prefix: str = "Human",
            ai_prefix: str = "AI",
            max_token_limit: int = 2000,
            message_limit: int = 10,
    ) -> str:
        """Get text-formatted conversation history for short-term memory (for text-generation models)"""
        # 1. Retrieve message history
        messages = self.get_history_prompt_messages(max_token_limit, message_limit)

        # 2. Convert message list to text using LangChain's get_buffer_string()
        return get_buffer_string(messages, human_prefix, ai_prefix)
