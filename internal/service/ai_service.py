#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : ai_service.py
"""
import json
from dataclasses import dataclass
from typing import Generator
from uuid import UUID

from injector import inject
from internal.entity.ai_entity import OPTIMIZE_PROMPT_TEMPLATE
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from internal.exception import ForbiddenException
from internal.model import Account, Message
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .conversation_service import ConversationService


@inject
@dataclass
class AIService(BaseService):
    """AI service"""
    db: SQLAlchemy
    conversation_service: ConversationService

    def generate_suggested_questions_from_message_id(self, message_id: UUID, account: Account) -> list[str]:
        """Generate suggested follow-up questions based on a message ID and user account"""
        # 1. Retrieve the message and validate permissions
        message = self.get(Message, message_id)
        if not message or message.created_by != account.id:
            raise ForbiddenException("This message does not exist or you do not have permission to access it")

        # 2. Build conversation history context
        histories = f"Human: {message.query}\nAI: {message.answer}"

        # 3. Call conversation service to generate suggested questions
        return self.conversation_service.generate_suggested_questions(histories)

    @classmethod
    def optimize_prompt(cls, prompt: str) -> Generator[str, None, None]:
        """Optimize the provided prompt using an LLM"""
        # 1. Build the prompt optimization template
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", OPTIMIZE_PROMPT_TEMPLATE),
            ("human", "{prompt}")
        ])

        # 2. Construct the LLM instance
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)

        # 3. Build the optimization chain
        optimize_chain = prompt_template | llm | StrOutputParser()

        # 4. Stream responses from the chain
        for optimize_prompt in optimize_chain.stream({"prompt": prompt}):
            # 5. Format and return streamed response event
            data = {"optimize_prompt": optimize_prompt}
            yield f"event: optimize_prompt\ndata: {json.dumps(data)}\n\n"
