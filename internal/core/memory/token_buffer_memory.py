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
    """Token-based buffer memory component."""
    db: SQLAlchemy  # Database instance
    conversation: Conversation  # Conversation model
    model_instance: BaseLanguageModel  # LLM instance

    def get_history_prompt_messages(
            self,
            max_token_limit: int = 2000,
            message_limit: int = 10,
    ) -> list[AnyMessage]:
        """
        Retrieve the historical message list for the specified conversation
        based on token and message count limits.

        Args:
            max_token_limit: Maximum number of tokens allowed in the buffer.
            message_limit: Maximum number of messages to retrieve.

        Returns:
            A list of LangChain-compatible messages.
        """
        # 1. Check if the conversation exists; if not, return an empty list.
        if self.conversation is None:
            return []

        # 2. Query the messages for this conversation in descending order by time,
        # filtering for valid, non-deleted, normal-status messages with non-empty answers.
        messages = (
            self.db.session.query(Message)
            .filter(
                Message.conversation_id == self.conversation.id,
                Message.answer != "",
                Message.is_deleted == False,
                Message.status == MessageStatus.NORMAL,
            )
            .order_by(desc("created_at"))
            .limit(message_limit)
            .all()
        )
        messages = list(reversed(messages))  # Reverse to chronological order

        # 3. Convert the messages into LangChain-compatible message objects.
        prompt_messages = []
        for message in messages:
            prompt_messages.extend([
                HumanMessage(content=message.query),
                AIMessage(content=message.answer),
            ])

        # 4. Use LangChain’s trim_messages() to truncate messages based on token count.
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
        """
        Retrieve the historical conversation text as a single prompt string.
        This serves as the short-term memory representation for text generation models.

        Args:
            human_prefix: Prefix label for human messages.
            ai_prefix: Prefix label for AI messages.
            max_token_limit: Maximum number of tokens allowed in the buffer.
            message_limit: Maximum number of messages to retrieve.

        Returns:
            A formatted text string representing conversation history.
        """
        # 1. Retrieve historical messages based on the provided limits.
        messages = self.get_history_prompt_messages(max_token_limit, message_limit)

        # 2. Convert the message list to text using LangChain’s get_buffer_string().
        return get_buffer_string(messages, human_prefix, ai_prefix)
