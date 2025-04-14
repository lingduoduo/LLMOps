#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : app_handler.py
"""
import uuid
from dataclasses import dataclass
from operator import itemgetter
from typing import Any, Dict

from injector import inject
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.documents import Document
from langchain_core.memory import BaseMemory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableConfig
from langchain_core.tracers import Run
from langchain_openai import ChatOpenAI

from internal.schema.app_schema import CompletionReq
from internal.service import AppService, VectorDatabaseService
from pkg.response import success_json, validate_error_json, success_message


@inject
@dataclass
class AppHandler:
    """Application Controller"""
    app_service: AppService
    vector_database_service: VectorDatabaseService

    def create_app(self):
        """Calls the service to create a new app record"""
        app = self.app_service.create_app()
        return success_message(f"Application successfully created with ID: {app.id}")

    def get_app(self, id: uuid.UUID):
        """Retrieves an app by its ID"""
        app = self.app_service.get_app(id)
        return success_message(f"Application successfully retrieved. Name: {app.name}")

    def update_app(self, id: uuid.UUID):
        """Updates an app by its ID"""
        app = self.app_service.update_app(id)
        return success_message(f"Application successfully updated. New name: {app.name}")

    def delete_app(self, id: uuid.UUID):
        """Deletes an app by its ID"""
        app = self.app_service.delete_app(id)
        return success_message(f"Application successfully deleted with ID: {app.id}")

    def completion(self):
        """Chat interface"""
        # 1. Extract input from the API request (POST)
        req = CompletionReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Initialize the OpenAI client and send a request
        client = ChatOpenAI()

        # 3. Get the response and pass it to the frontend
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system",
                 "content": "You are a chatbot developed by OpenAI. Respond to user input accordingly."},
                {"role": "user",
                 "content": req.query.data},
            ]
        )

        content = completion.choices[0].message.content

        return success_json({"content": content})

    @classmethod
    def _load_memory_variables(cls, input: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
        """Load memory variable information"""
        configurable = config.get("configurable", {})
        configurable_memory = configurable.get("memory", None)
        if configurable_memory is not None and isinstance(configurable_memory, BaseMemory):
            return configurable_memory.load_memory_variables(input)
        return {"history": []}

    @classmethod
    def _save_context(cls, run_obj: Run, config: RunnableConfig) -> None:
        """Store context information into the memory entity"""
        configurable = config.get("configurable", {})
        configurable_memory = configurable.get("memory", None)
        if configurable_memory is not None and isinstance(configurable_memory, BaseMemory):
            configurable_memory.save_context(run_obj.inputs, run_obj.outputs)

    def debug(self, app_id: uuid.UUID):
        """Chat Interface"""

        # 1. Extract input from the interface (POST request)
        req = CompletionReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Create the prompt and memory
        system_prompt = (
            "You are a powerful chatbot capable of answering user questions "
            "based on the given context and conversation history.\n\n<context>{context}</context>"
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder("history"),  # Placeholder for conversation history
            ("human", "{query}"),  # User's query
        ])

        memory = ConversationBufferWindowMemory(
            k=3,  # Tracks the last 3 exchanges in memory
            input_key="query",
            output_key="output",
            return_messages=True,
            chat_memory=FileChatMessageHistory("./storage/memory/chat_history.txt"),
        )

        # 3. Create the language model
        llm = ChatOpenAI(model="gpt-3.5-turbo-16k")

        # 4. Create the application chain
        retriever = self.vector_database_service.get_retriever() | self.vector_database_service.combine_documents
        chain = (RunnablePassthrough.assign(
            history=RunnableLambda(self._load_memory_variables) | itemgetter("history"),
            context=itemgetter("query") | retriever
        ) | prompt | llm | StrOutputParser()).with_listeners(on_end=self._save_context)

        # 5. Invoke the chain to generate content
        chain_input = {"query": req.query.data}
        content = chain.invoke(chain_input, config={"configurable": {"memory": memory}})

        return success_json({"content": content})

    @classmethod
    def _combine_documents(cls, documents: list[Document]) -> str:
        """Combine a list of input documents into a single string"""
        return "\n\n".join([document.page_content for document in documents])

    def ping(self):
        """Health check endpoint"""
        # raise FailException("Data not found")
        return {"ping": "pong"}
