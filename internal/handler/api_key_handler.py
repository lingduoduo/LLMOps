#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : api_key_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject
from internal.schema.api_key_schema import (
    CreateApiKeyReq,
    UpdateApiKeyReq,
    UpdateApiKeyIsActiveReq,
    GetApiKeysWithPageResp,
)

from internal.service import ApiKeyService
from pkg.paginator import PaginatorReq, PageModel
from pkg.response import validate_error_json, success_message, success_json


@inject
@dataclass
class ApiKeyHandler:
    """API Key Handler"""
    api_key_service: ApiKeyService

    @login_required
    def create_api_key(self):
        """Create an API key"""
        # 1. Extract and validate the request
        req = CreateApiKeyReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to create API key
        self.api_key_service.create_api_key(req, current_user)

        return success_message("API key created successfully")

    @login_required
    def delete_api_key(self, api_key_id: UUID):
        """Delete an API key by ID"""
        self.api_key_service.delete_api_key(api_key_id, current_user)
        return success_message("API key deleted successfully")

    @login_required
    def update_api_key(self, api_key_id: UUID):
        """Update API key by ID using the provided data"""
        # 1. Extract and validate the request
        req = UpdateApiKeyReq()
        print(req.data)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to update API key
        self.api_key_service.update_api_key(api_key_id, current_user, **req.data)

        return success_message("API key updated successfully")

    @login_required
    def update_api_key_is_active(self, api_key_id: UUID):
        """Update the activation status of an API key"""
        # 1. Extract and validate the request
        req = UpdateApiKeyIsActiveReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to update active status
        self.api_key_service.update_api_key(api_key_id, current_user, **req.data)

        return success_message("API key activation status updated successfully")

    @login_required
    def get_api_keys_with_page(self):
        """Get a paginated list of API keys for the current account"""
        # 1. Extract and validate pagination parameters
        req = PaginatorReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to retrieve data
        api_keys, paginator = self.api_key_service.get_api_keys_with_page(req, current_user)

        # 3. Build and return response
        resp = GetApiKeysWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(api_keys), paginator=paginator))
