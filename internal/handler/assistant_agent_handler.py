#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : assistant_agent_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject
from internal.schema.assistant_agent_schema import (
    AssistantAgentChat,
    GetAssistantAgentMessagesWithPageReq,
    GetAssistantAgentMessagesWithPageResp,
)

from internal.service import AssistantAgentService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, compact_generate_response, success_json, success_message


@inject
@dataclass
class AssistantAgentHandler:
    """Assistant Agent handler"""
    assistant_agent_service: AssistantAgentService

    @login_required
    def assistant_agent_chat(self):
        """Chat with the Assistant Agent"""
        # 1. Extract request data and validate
        req = AssistantAgentChat()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to generate chat response
        response = self.assistant_agent_service.chat(req.query.data, current_user)

        return compact_generate_response(response)

    @login_required
    def stop_assistant_agent_chat(self, task_id: UUID):
        """Stop the ongoing chat with the Assistant Agent"""
        self.assistant_agent_service.stop_chat(task_id, current_user)
        return success_message("Successfully stopped Assistant Agent chat")

    @login_required
    def get_assistant_agent_messages_with_page(self):
        """Retrieve paginated message list for the Assistant Agent conversation"""
        # 1. Extract request parameters and validate
        req = GetAssistantAgentMessagesWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Fetch messages and pagination info from the service
        messages, paginator = self.assistant_agent_service.get_conversation_messages_with_page(
            req, current_user
        )

        # 3. Build response schema
        resp = GetAssistantAgentMessagesWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(messages), paginator=paginator))

    @login_required
    def delete_assistant_agent_conversation(self):
        """Clear/Delete the conversation history with the Assistant Agent"""
        # 1. Call service to clear conversation
        self.assistant_agent_service.delete_conversation(current_user)

        # 2. Return success response
        return success_message("Successfully cleared Assistant Agent conversation")
