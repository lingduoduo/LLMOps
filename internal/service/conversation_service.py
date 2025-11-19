#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : conversation_service.py
"""
import logging
from dataclasses import dataclass

from injector import inject
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from internal.entity.conversation_entity import (
    SUMMARIZER_TEMPLATE,
    CONVERSATION_NAME_TEMPLATE,
    ConversationInfo,
    SUGGESTED_QUESTIONS_TEMPLATE,
    SuggestedQuestions,
)
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class ConversationService(BaseService):
    """Conversation Service"""
    db: SQLAlchemy

    @classmethod
    def summary(cls, human_message: str, ai_message: str, old_summary: str = "") -> str:
        """Generate a new summary based on the given human message, AI message, and the previous summary"""
        # 1. Create the prompt
        prompt = ChatPromptTemplate.from_template(SUMMARIZER_TEMPLATE)

        # 2. Build the LLM instance with a low temperature to reduce hallucinations
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)

        # 3. Build the chain
        summary_chain = prompt | llm | StrOutputParser()

        # 4. Invoke the chain to get a new summary
        new_summary = summary_chain.invoke({
            "summary": old_summary,
            "new_lines": f"Human: {human_message}\nAI: {ai_message}",
        })

        return new_summary

    @classmethod
    def generate_conversation_name(cls, query: str) -> str:
        """Generate a conversation name based on the provided query, keeping the same language as the user input"""
        # 1. Create the prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", CONVERSATION_NAME_TEMPLATE),
            ("human", "{query}")
        ])

        # 2. Build the LLM instance with a low temperature to reduce hallucinations
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        structured_llm = llm.with_structured_output(ConversationInfo)

        # 3. Build the chain
        chain = prompt | structured_llm

        # 4. Preprocess and truncate overly long queries
        if len(query) > 2000:
            query = query[:300] + "...[TRUNCATED]..." + query[-300:]
        query = query.replace("\n", " ")

        # 5. Invoke the chain and get the conversation info
        conversation_info = chain.invoke({"query": query})

        # 6. Extract the conversation name
        name = "New Conversation"
        try:
            if conversation_info and hasattr(conversation_info, "subject"):
                name = conversation_info.subject
        except Exception as e:
            logging.exception(
                f"Error extracting conversation name, conversation_info: {conversation_info}, error: {str(e)}")
        if len(name) > 75:
            name = name[:75] + "..."

        return name

    @classmethod
    def generate_suggested_questions(cls, histories: str) -> list[str]:
        """Generate up to 3 suggested questions based on the given conversation history"""
        # 1. Create the prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", SUGGESTED_QUESTIONS_TEMPLATE),
            ("human", "{histories}")
        ])

        # 2. Build the LLM instance with a low temperature to reduce hallucinations
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        structured_llm = llm.with_structured_output(SuggestedQuestions)

        # 3. Build the chain
        chain = prompt | structured_llm

        # 4. Invoke the chain to get the suggested questions
        suggested_questions = chain.invoke({"histories": histories})

        # 5. Extract the question list
        questions = []
        try:
            if suggested_questions and hasattr(suggested_questions, "questions"):
                questions = suggested_questions.questions
        except Exception as e:
            logging.exception(
                f"Error generating suggested questions, suggested_questions: {suggested_questions}, error: {str(e)}")
        if len(questions) > 3:
            questions = questions[:3]

        return questions
