#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : conversation_service.py
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from threading import Thread
from typing import Any
from uuid import UUID

from flask import Flask, current_app
from injector import inject
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sqlalchemy import desc
from sqlalchemy.orm import joinedload

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.entity.conversation_entity import (
    SUMMARIZER_TEMPLATE,
    CONVERSATION_NAME_TEMPLATE,
    ConversationInfo,
    SUGGESTED_QUESTIONS_TEMPLATE,
    SuggestedQuestions,
    InvokeFrom,
    MessageStatus,
)
from internal.exception import NotFoundException
from internal.model import Conversation, Message, MessageAgentThought, Account
from internal.schema.conversation_schema import GetConversationMessagesWithPageReq
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class ConversationService(BaseService):
    """Conversation service"""
    db: SQLAlchemy

    @classmethod
    def summary(cls, human_message: str, ai_message: str, old_summary: str = "") -> str:
        """Generate a new summary based on the human message, AI message, and the existing summary."""
        # 1. Create prompt
        prompt = ChatPromptTemplate.from_template(SUMMARIZER_TEMPLATE)

        # 2. Initialize the LLM with lower temperature to reduce hallucinations
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)

        # 3. Build the chain
        summary_chain = prompt | llm | StrOutputParser()

        # 4. Invoke the chain to generate a new summary
        new_summary = summary_chain.invoke({
            "summary": old_summary,
            "new_lines": f"Human: {human_message}\nAI: {ai_message}",
        })

        return new_summary

    @classmethod
    def generate_conversation_name(cls, query: str) -> str:
        """Generate a conversation name based on the query, keeping the same language as user input."""
        # 1. Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", CONVERSATION_NAME_TEMPLATE),
            ("human", "{query}")
        ])

        # 2. Initialize the LLM with zero temperature for deterministic output
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        structured_llm = llm.with_structured_output(ConversationInfo)

        # 3. Build the chain
        chain = prompt | structured_llm

        # 4. Normalize and truncate overly long queries
        if len(query) > 2000:
            query = query[:300] + "...[TRUNCATED]..." + query[-300:]
        query = query.replace("\n", " ")

        # 5. Invoke the chain to generate conversation info
        conversation_info = chain.invoke({"query": query})

        # 6. Extract conversation name
        name = "New Conversation"
        try:
            if conversation_info and hasattr(conversation_info, "subject"):
                name = conversation_info.subject
        except Exception as e:
            logging.exception(
                "Failed to extract conversation name, conversation_info: %(conversation_info)s, error: %(error)s",
                {"conversation_info": conversation_info, "error": e},
            )

        if len(name) > 75:
            name = name[:75] + "..."

        return name

    @classmethod
    def generate_suggested_questions(cls, histories: str) -> list[str]:
        """Generate up to three suggested follow-up questions based on conversation history."""
        # 1. Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", SUGGESTED_QUESTIONS_TEMPLATE),
            ("human", "{histories}")
        ])

        # 2. Initialize the LLM with zero temperature
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        structured_llm = llm.with_structured_output(SuggestedQuestions)

        # 3. Build the chain
        chain = prompt | structured_llm

        # 4. Invoke the chain to generate suggested questions
        suggested_questions = chain.invoke({"histories": histories})

        # 5. Extract questions
        questions = []
        try:
            if suggested_questions and hasattr(suggested_questions, "questions"):
                questions = suggested_questions.questions
        except Exception as e:
            logging.exception(
                "Failed to generate suggested questions, suggested_questions: %(suggested_questions)s, error: %(error)s",
                {"suggested_questions": suggested_questions, "error": e},
            )

        if len(questions) > 3:
            questions = questions[:3]

        return questions

    def save_agent_thoughts(
            self,
            account_id: UUID,
            app_id: UUID,
            app_config: dict[str, Any],
            conversation_id: UUID,
            message_id: UUID,
            agent_thoughts: list[AgentThought],
    ):
        """Persist agent reasoning steps."""
        # 1. Initialize position index and total latency
        position = 0
        latency = 0

        # 2. Re-fetch conversation and message to ensure they are managed by the current session
        conversation = self.get(Conversation, conversation_id)
        message = self.get(Message, message_id)

        # 3. Iterate through all agent reasoning steps
        for agent_thought in agent_thoughts:
            # 4. Store reasoning steps such as memory recall, thoughts, messages, actions, and retrievals
            if agent_thought.event in [
                QueueEvent.LONG_TERM_MEMORY_RECALL,
                QueueEvent.AGENT_THOUGHT,
                QueueEvent.AGENT_MESSAGE,
                QueueEvent.AGENT_ACTION,
                QueueEvent.DATASET_RETRIEVAL,
            ]:
                # 5. Update position and latency
                position += 1
                latency += agent_thought.latency

                # 6. Persist agent reasoning step
                self.create(
                    MessageAgentThought,
                    app_id=app_id,
                    conversation_id=conversation.id,
                    message_id=message.id,
                    invoke_from=InvokeFrom.DEBUGGER,
                    created_by=account_id,
                    position=position,
                    event=agent_thought.event,
                    thought=agent_thought.thought,
                    observation=agent_thought.observation,
                    tool=agent_thought.tool,
                    tool_input=agent_thought.tool_input,
                    # Message-related fields
                    message=agent_thought.message,
                    message_token_count=agent_thought.message_token_count,
                    message_unit_price=agent_thought.message_unit_price,
                    message_price_unit=agent_thought.message_price_unit,
                    # Answer-related fields
                    answer=agent_thought.answer,
                    answer_token_count=agent_thought.answer_token_count,
                    answer_unit_price=agent_thought.answer_unit_price,
                    answer_price_unit=agent_thought.answer_price_unit,
                    # Agent statistics
                    total_token_count=agent_thought.total_token_count,
                    total_price=agent_thought.total_price,
                    latency=agent_thought.latency,
                )

            # 7. If the event is an agent message
            if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                # 8. Update message content
                self.update(
                    message,
                    message=agent_thought.message,
                    message_token_count=agent_thought.message_token_count,
                    message_unit_price=agent_thought.message_unit_price,
                    message_price_unit=agent_thought.message_price_unit,
                    answer=agent_thought.answer,
                    answer_token_count=agent_thought.answer_token_count,
                    answer_unit_price=agent_thought.answer_unit_price,
                    answer_price_unit=agent_thought.answer_price_unit,
                    total_token_count=agent_thought.total_token_count,
                    total_price=agent_thought.total_price,
                    latency=latency,
                )

                # 9. Generate conversation summary if long-term memory is enabled
                if app_config["long_term_memory"]["enable"]:
                    Thread(
                        target=self._generate_summary_and_update,
                        kwargs={
                            "flask_app": current_app._get_current_object(),
                            "conversation_id": conversation.id,
                            "query": message.query,
                            "answer": agent_thought.answer,
                        },
                    ).start()

                # 10. Generate conversation name for new conversations
                if conversation.is_new:
                    Thread(
                        target=self._generate_conversation_name_and_update,
                        kwargs={
                            "flask_app": current_app._get_current_object(),
                            "conversation_id": conversation.id,
                            "query": message.query,
                        }
                    ).start()

            # 11. If timeout, stop, or error occurs, update message status
            if agent_thought.event in [QueueEvent.TIMEOUT, QueueEvent.STOP, QueueEvent.ERROR]:
                self.update(
                    message,
                    status=agent_thought.event,
                    error=agent_thought.observation,
                )
                break

    def _generate_summary_and_update(
            self,
            flask_app: Flask,
            conversation_id: UUID,
            query: str,
            answer: str,
    ):
        with flask_app.app_context():
            # 1. Retrieve conversation
            conversation = self.get(Conversation, conversation_id)

            # 2. Generate updated summary
            new_summary = self.summary(query, answer, conversation.summary)

            # 3. Update conversation summary
            self.update(conversation, summary=new_summary)

    def _generate_conversation_name_and_update(
            self,
            flask_app: Flask,
            conversation_id: UUID,
            query: str
    ) -> None:
        """Generate and update conversation name."""
        with flask_app.app_context():
            # 1. Retrieve conversation
            conversation = self.get(Conversation, conversation_id)

            # 2. Generate new conversation name
            new_conversation_name = self.generate_conversation_name(query)

            # 3. Update conversation name
            self.update(conversation, name=new_conversation_name)

    def get_conversation(self, conversation_id: UUID, account: Account) -> Conversation:
        """Retrieve a conversation by ID and account."""
        # 1. Fetch conversation
        conversation = self.get(Conversation, conversation_id)
        if (
                not conversation
                or conversation.created_by != account.id
                or conversation.is_deleted
        ):
            raise NotFoundException("The conversation does not exist or has been deleted.")

        return conversation

    def get_message(self, message_id: UUID, account: Account) -> Message:
        """Retrieve a message by ID and account."""
        # 1. Fetch message
        message = self.get(Message, message_id)
        if (
                not message
                or message.created_by != account.id
                or message.is_deleted
        ):
            raise NotFoundException("The message does not exist or has been deleted.")

        return message

    def get_conversation_messages_with_page(
            self,
            conversation_id: UUID,
            req: GetConversationMessagesWithPageReq,
            account: Account,
    ) -> tuple[list[Message], Paginator]:
        """Retrieve paginated messages for a conversation."""
        # 1. Validate conversation and permissions
        conversation = self.get_conversation(conversation_id, account)

        # 2. Build paginator
        paginator = Paginator(db=self.db, req=req)
        filters = []
        if req.created_at.data:
            # 3. Convert timestamp to datetime
            created_at_datetime = datetime.fromtimestamp(req.created_at.data)
            filters.append(Message.created_at <= created_at_datetime)

        # 4. Execute paginated query
        messages = paginator.paginate(
            self.db.session.query(Message)
            .options(joinedload(Message.agent_thoughts))
            .filter(
                Message.conversation_id == conversation.id,
                Message.status.in_([MessageStatus.STOP, MessageStatus.NORMAL]),
                Message.answer != "",
                ~Message.is_deleted,
                *filters,
            )
            .order_by(desc("created_at"))
        )

        return messages, paginator

    def delete_conversation(self, conversation_id: UUID, account: Account) -> Conversation:
        """Delete a conversation by ID."""
        # 1. Retrieve conversation
        conversation = self.get_conversation(conversation_id, account)

        # 2. Mark conversation as deleted
        self.update(conversation, is_deleted=True)

        return conversation

    def delete_message(self, conversation_id: UUID, message_id: UUID, account: Account) -> Message:
        """Delete a message by ID."""
        # 1. Validate conversation
        conversation = self.get_conversation(conversation_id, account)

        # 2. Validate message
        message = self.get_message(message_id, account)

        # 3. Ensure message belongs to conversation
        if conversation.id != message.conversation_id:
            raise NotFoundException("The message does not belong to this conversation.")

        # 4. Mark message as deleted
        self.update(message, is_deleted=True)

        return message

    def update_conversation(self, conversation_id: UUID, account: Account, **kwargs) -> Conversation:
        """Update conversation fields."""
        # 1. Validate conversation
        conversation = self.get_conversation(conversation_id, account)

        # 2. Update conversation
        self.update(conversation, **kwargs)

        return conversation
