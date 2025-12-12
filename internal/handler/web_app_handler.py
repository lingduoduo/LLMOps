#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : web_app_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject
from internal.schema.web_app_schema import (
    GetWebAppResp,
    WebAppChatReq,
    GetConversationsReq,
    GetConversationsResp,
)

from internal.service import WebAppService
from pkg.response import success_json, validate_error_json, success_message, compact_generate_response


@inject
@dataclass
class WebAppHandler:
    """WebApp Handler"""
    web_app_service: WebAppService

    @login_required
    def get_web_app(self, token: str):
        """Retrieve basic WebApp information based on the provided token."""
        # 1. Call the service to get the application info using the token
        app = self.web_app_service.get_web_app(token)

        # 2. Build the response structure and return it
        resp = GetWebAppResp()

        return success_json(resp.dump(app))

    @login_required
    def web_app_chat(self, token: str):
        """Interact with the WebApp using the provided token and query parameters."""
        # 1. Extract and validate the request
        req = WebAppChatReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call the service to obtain the response
        response = self.web_app_service.web_app_chat(token, req, current_user)

        return compact_generate_response(response)

    @login_required
    def stop_web_app_chat(self, token: str, task_id: UUID):
        """Stop an ongoing conversation with the WebApp using the provided token and task_id."""
        self.web_app_service.stop_web_app_chat(token, task_id, current_user)
        return success_message("Successfully stopped WebApp conversation")

    @login_required
    def get_conversations(self, token: str):
        """Retrieve all conversation sessions under the specified WebApp (filtered by token + is_pinned)."""
        # 1. Extract and validate the request
        req = GetConversationsReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call the service to get the conversation list
        conversations = self.web_app_service.get_conversations(
            token, req.is_pinned.data, current_user
        )

        # 3. Build the response structure and return it
        resp = GetConversationsResp(many=True)

        return success_json(resp.dump(conversations))
