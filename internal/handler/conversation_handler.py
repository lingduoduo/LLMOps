#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : conversation_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject
from internal.schema.conversation_schema import (
    GetConversationMessagesWithPageReq,
    GetConversationMessagesWithPageResp,
    UpdateConversationNameReq,
    UpdateConversationIsPinnedReq,
)

from internal.service import ConversationService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_json, success_message


@inject
@dataclass
class ConversationHandler:
    """Conversation handler"""
    conversation_service: ConversationService

    @login_required
    def get_conversation_messages_with_page(self, conversation_id: UUID):
        """Get a paginated list of messages for the given conversation ID"""
        # 1. Extract request data and validate
        req = GetConversationMessagesWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to retrieve paginated messages
        messages, paginator = self.conversation_service.get_conversation_messages_with_page(
            conversation_id,
            req,
            current_user
        )

        # 3. Build and return response
        resp = GetConversationMessagesWithPageResp(many=True)
        return success_json(PageModel(list=resp.dump(messages), paginator=paginator))

    @login_required
    def delete_conversation(self, conversation_id: UUID):
        """Delete the specified conversation by conversation ID"""
        self.conversation_service.delete_conversation(conversation_id, current_user)
        return success_message("Conversation deleted successfully")

    @login_required
    def delete_message(self, conversation_id: UUID, message_id: UUID):
        """Delete the specified message by conversation ID and message ID"""
        self.conversation_service.delete_message(conversation_id, message_id, current_user)
        return success_message("Conversation message deleted successfully")

    @login_required
    def get_conversation_name(self, conversation_id: UUID):
        """Get the name of the specified conversation by conversation ID"""
        # 1. Retrieve conversation from service
        conversation = self.conversation_service.get_conversation(conversation_id, current_user)

        # 2. Build and return response
        return success_json({"name": conversation.name})

    @login_required
    def update_conversation_name(self, conversation_id: UUID):
        """Update the conversation name using conversation ID and name"""
        # 1. Extract request and validate
        req = UpdateConversationNameReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Update conversation name via service
        self.conversation_service.update_conversation(
            conversation_id,
            current_user,
            name=req.name.data
        )
        return success_message("Conversation name updated successfully")

    @login_required
    def update_conversation_is_pinned(self, conversation_id: UUID):
        """Update the pinned status of a conversation using conversation ID and is_pinned"""
        # 1. Extract request and validate
        req = UpdateConversationIsPinnedReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Update pinned status via service
        self.conversation_service.update_conversation(
            conversation_id,
            current_user,
            is_pinned=req.is_pinned.data
        )
        return success_message("Conversation pinned status updated successfully")
