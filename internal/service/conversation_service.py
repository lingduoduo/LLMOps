#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : conversation_service.py
"""
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from flask import Flask
from injector import inject
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from internal.entity.conversation_entity import (
    SUMMARIZER_TEMPLATE,
    CONVERSATION_NAME_TEMPLATE,
    ConversationInfo,
    SUGGESTED_QUESTIONS_TEMPLATE,
    SuggestedQuestions, InvokeFrom,
)
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from ..core.agent.entities.queue_entity import AgentThought, QueueEvent
from ..model import Conversation, Message, MessageAgentThought


@inject
@dataclass
class ConversationService(BaseService):
    """Conversation service"""
    db: SQLAlchemy

    @classmethod
    def summary(cls, human_message: str, ai_message: str, old_summary: str = "") -> str:
        """Generate a new summary based on the human message, AI message, and the previous summary"""
        # 1. Create the prompt
        prompt = ChatPromptTemplate.from_template(SUMMARIZER_TEMPLATE)

        # 2. Build the LLM instance and set a lower temperature to reduce hallucinations
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)

        # 3. Build the chain
        summary_chain = prompt | llm | StrOutputParser()

        # 4. Invoke the chain and get the new summary
        new_summary = summary_chain.invoke({
            "summary": old_summary,
            "new_lines": f"Human: {human_message}\nAI: {ai_message}",
        })

        return new_summary

    @classmethod
    def generate_conversation_name(cls, query: str) -> str:
        """Generate the conversation name based on the query and keep the language consistent with the user's input"""
        # 1. Create the prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", CONVERSATION_NAME_TEMPLATE),
            ("human", "{query}")
        ])

        # 2. Build the LLM instance and set a low temperature to reduce hallucinations
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        structured_llm = llm.with_structured_output(ConversationInfo)

        # 3. Build the chain
        chain = prompt | structured_llm

        # 4. Normalize and truncate the query if it is too long
        if len(query) > 2000:
            query = query[:300] + "...[TRUNCATED]..." + query[-300:]
        query = query.replace("\n", " ")

        # 5. Invoke the chain and get conversation info
        conversation_info = chain.invoke({"query": query})

        # 6. Extract the conversation name
        name = "New Conversation"
        try:
            if conversation_info and hasattr(conversation_info, "subject"):
                name = conversation_info.subject
        except Exception as e:
            logging.exception(
                f"Error extracting conversation name, conversation_info: {conversation_info}, error: {str(e)}"
            )
        if len(name) > 75:
            name = name[:75] + "..."

        return name

    @classmethod
    def generate_suggested_questions(cls, histories: str) -> list[str]:
        """Generate up to 3 suggested follow-up questions based on the conversation history"""
        # 1. Create the prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", SUGGESTED_QUESTIONS_TEMPLATE),
            ("human", "{histories}")
        ])

        # 2. Build the LLM instance and set a low temperature to reduce hallucinations
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        structured_llm = llm.with_structured_output(SuggestedQuestions)

        # 3. Build the chain
        chain = prompt | structured_llm

        # 4. Invoke the chain and get the suggested questions
        suggested_questions = chain.invoke({"histories": histories})

        # 5. Extract the list of suggested questions
        questions = []
        try:
            if suggested_questions and hasattr(suggested_questions, "questions"):
                questions = suggested_questions.questions
        except Exception as e:
            logging.exception(
                f"Error generating suggested questions, suggested_questions: {suggested_questions}, error: {str(e)}"
            )
        if len(questions) > 3:
            questions = questions[:3]

        return questions

    def save_agent_thoughts(
            self,
            flask_app: Flask,
            account_id: UUID,
            app_id: UUID,
            app_config: dict[str, Any],
            conversation_id: UUID,
            message_id: UUID,
            agent_thoughts: list[AgentThought],
    ):
        """Persist agent reasoning step messages"""
        with flask_app.app_context():
            # 1. Define variables for reasoning step position and total latency
            position = 0
            latency = 0

            # 2. In the child thread, re-fetch the conversation and message
            #    so they are properly managed by the child thread's session
            conversation = self.get(Conversation, conversation_id)
            message = self.get(Message, message_id)

            # 3. Iterate over all agent reasoning steps and persist them
            for agent_thought in agent_thoughts:
                # 4. Persist steps such as long-term memory recall, reasoning,
                #    messages, actions, and dataset retrieval
                if agent_thought.event in [
                    QueueEvent.LONG_TERM_MEMORY_RECALL,
                    QueueEvent.AGENT_THOUGHT,
                    QueueEvent.AGENT_MESSAGE,
                    QueueEvent.AGENT_ACTION,
                    QueueEvent.DATASET_RETRIEVAL,
                ]:
                    # 5. Update position and total latency
                    position += 1
                    latency += agent_thought.latency

                    # 6. Create a MessageAgentThought record
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
                        message=agent_thought.message,
                        answer=agent_thought.answer,
                        latency=agent_thought.latency,
                    )

                # 7. Check whether the event is AGENT_MESSAGE
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    # 8. Update the message record
                    self.update(
                        message,
                        message=agent_thought.message,
                        answer=agent_thought.answer,
                        latency=latency,
                    )

                    # 9. Check whether long-term memory is enabled
                    if app_config["long_term_memory"]["enable"]:
                        new_summary = self.summary(
                            message.query,
                            agent_thought.answer,
                            conversation.summary
                        )
                        self.update(
                            conversation,
                            summary=new_summary,
                        )

                    # 10. Handle generation of a new conversation name
                    if conversation.is_new:
                        new_conversation_name = self.generate_conversation_name(message.query)
                        self.update(
                            conversation,
                            name=new_conversation_name,
                        )

                # 11. If the event is TIMEOUT, STOP, or ERROR, update the message status
                if agent_thought.event in [QueueEvent.TIMEOUT, QueueEvent.STOP, QueueEvent.ERROR]:
                    self.update(
                        message,
                        status=agent_thought.event,
                        error=agent_thought.observation,
                    )
                    break
