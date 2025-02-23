#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : app_handler.py
"""
import os
import uuid
from dataclasses import dataclass

from injector import inject
from openai import OpenAI

from internal.exception import FailException
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
        client = OpenAI(base_url=os.getenv("OPENAI_API_BASE"))

        # 3. Get the response and pass it to the frontend
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo-16k",
            messages=[
                {"role": "system",
                 "content": "You are a chatbot developed by OpenAI. Respond to user input accordingly."},
                {"role": "user", "content": req.query.data},
            ]
        )

        content = completion.choices[0].message.content

        return success_json({"content": content})

    def ping(self):
        """Health check endpoint"""
        raise FailException("Data not found")
        # return {"ping": "pong"}
