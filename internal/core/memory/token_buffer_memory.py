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
        """Get historical messages for a conversation according to token limit and message count limit."""
        # 1. If the conversation does not exist, return an empty list
        if self.conversation is None:
            return []

        # 2. Query message list for the conversation:
        #    - ordered by creation time (descending)
        #    - answer not empty
        #    - not soft deleted
        #    - message status in NORMAL / STOP / TIMEOUT
        messages = (
            self.db.session.query(Message)
            .filter(
                Message.conversation_id == self.conversation.id,
                Message.answer != "",
                Message.is_deleted == False,
                Message.status.in_([
                    MessageStatus.NORMAL,
                    MessageStatus.STOP,
                    MessageStatus.TIMEOUT
                ]),
            )
            .order_by(desc("created_at"))
            .limit(message_limit)
            .all()
        )

        # Reverse to restore chronological order
        messages = list(reversed(messages))

        # 3. Convert DB messages into LangChain-compatible message objects
        prompt_messages = []
        for message in messages:
            prompt_messages.extend([
                HumanMessage(content=message.query),
                AIMessage(content=message.answer),
            ])

        # 4. Use LangChain's trim_messages to prune the list based on token count
        return trim_messages(
            messages=prompt_messages,
            max_tokens=max_token_limit,
            token_counter=self.model_instance,
            strategy="last",
            start_on="human",
            end_on="ai",
        )

    def get_history_prompt_text(
            self,
            human_prefix: str = "Human",
            ai_prefix: str = "AI",
            max_token_limit: int = 2000,
            message_limit: int = 10,
    ) -> str:
        """Convert conversation history into a text buffer (short-term memory text for LLMs)."""
        # 1. Get historical message list
        messages = self.get_history_prompt_messages(max_token_limit, message_limit)

        # 2. Convert message list to plain text using LangChain's get_buffer_string
        return get_buffer_string(messages, human_prefix, ai_prefix)
