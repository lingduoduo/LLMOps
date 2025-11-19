#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : api_tool_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.schema.api_tool_schema import (
    ValidateOpenAPISchemaReq,
    CreateApiToolReq,
    GetApiToolProviderResp,
    GetApiToolResp,
    GetApiToolProvidersWithPageReq,
    GetApiToolProvidersWithPageResp,
    UpdateApiToolProviderReq,
)
from internal.service import ApiToolService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_message, success_json


@inject
@dataclass
class ApiToolHandler:
    """Custom API Plugin Handler"""
    api_tool_service: ApiToolService

    @login_required
    def get_api_tool_providers_with_page(self):
        """Get a paginated list of API tool providers"""
        req = GetApiToolProvidersWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        api_tool_providers, paginator = self.api_tool_service.get_api_tool_providers_with_page(req, current_user)

        resp = GetApiToolProvidersWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(api_tool_providers), paginator=paginator))

    @login_required
    def create_api_tool_provider(self):
        """Create a custom API tool"""
        req = CreateApiToolReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.api_tool_service.create_api_tool(req, current_user)

        return success_message("Custom API plugin created successfully")

    @login_required
    def update_api_tool_provider(self, provider_id: UUID):
        """Update information for a custom API tool provider"""
        req = UpdateApiToolProviderReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.api_tool_service.update_api_tool_provider(provider_id, req, current_user)

        return success_message("Custom API plugin updated successfully")

    @login_required
    def get_api_tool(self, provider_id: UUID, tool_name: str):
        """Get detailed information for a tool by provider_id and tool_name"""
        api_tool = self.api_tool_service.get_api_tool(provider_id, tool_name, current_user)

        resp = GetApiToolResp()

        return success_json(resp.dump(api_tool))

    @login_required
    def get_api_tool_provider(self, provider_id: UUID):
        """Get raw information for a tool provider by provider_id"""
        api_tool_provider = self.api_tool_service.get_api_tool_provider(provider_id, current_user)

        resp = GetApiToolProviderResp()

        return success_json(resp.dump(api_tool_provider))

    @login_required
    def delete_api_tool_provider(self, provider_id: UUID):
        """Delete the tool provider information by provider_id"""
        self.api_tool_service.delete_api_tool_provider(provider_id, current_user)

        return success_message("Custom API plugin deleted successfully")

    @login_required
    def validate_openapi_schema(self):
        """Validate whether the provided openapi_schema string is correct"""
        req = ValidateOpenAPISchemaReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.api_tool_service.parse_openapi_schema(req.openapi_schema.data)

        return success_message("Data validation successful")
