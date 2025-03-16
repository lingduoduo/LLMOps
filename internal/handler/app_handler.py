#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : app_handler.py
"""
import uuid
from dataclasses import dataclass
from operator import itemgetter

from injector import inject
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI
from openai import OpenAI

from internal.schema.app_schema import CompletionReq
from internal.service import AppService
from pkg.response import success_json, validate_error_json, success_message


@inject
@dataclass
class AppHandler:
    """Application Controller"""
    app_service: AppService

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
        client = OpenAI()

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

    def debug(self, app_id: uuid.UUID):
        """Chat Interface"""

        # 1. Extract input from the interface (POST request)
        req = CompletionReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Create the prompt and memory
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a powerful chatbot that can respond to user questions accordingly."),
            MessagesPlaceholder("history"),  # Placeholder for conversation history
            ("human", "{query}"),  # User's query
        ])

        memory = ConversationBufferWindowMemory(
            k=3,  # Tracks the last 3 exchanges in memory
            input_key="query",  # Key for the user's query input
            output_key="output",  # Key for the AI's output
            return_messages=True,  # Ensures messages are returned as part of the response
            chat_memory=FileChatMessageHistory("./storage/memory/chat_history.txt"),  # Stores chat history in a file
        )

        # 3. Create the language model
        llm = ChatOpenAI(model="gpt-3.5-turbo-16k")

        # 4. Create the application chain
        chain = RunnablePassthrough.assign(
            history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
        ) | prompt | llm | StrOutputParser()

        # 5. Invoke the chain to generate content
        chain_input = {"query": req.query.data}
        content = chain.invoke(chain_input)
        memory.save_context(chain_input, {"output": content})

        return success_json({"content": content})

    def ping(self):
        """Health check endpoint"""
        # raise FailException("Data not found")
        return {"ping": "pong"}
