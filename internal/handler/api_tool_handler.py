#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/8/1 10:16
@Author  : thezehui@gmail.com
@File    : api_tool_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
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
    """Handler for custom API plugins"""
    api_tool_service: ApiToolService

    def get_api_tool_providers_with_page(self):
        """Retrieve a paginated list of API tool providers"""
        req = GetApiToolProvidersWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        api_tool_providers, paginator = self.api_tool_service.get_api_tool_providers_with_page(req)

        resp = GetApiToolProvidersWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(api_tool_providers), paginator=paginator))

    def create_api_tool_provider(self):
        """Create a new custom API tool"""
        req = CreateApiToolReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.api_tool_service.create_api_tool(req)

        return success_message("Custom API plugin created successfully")

    def update_api_tool_provider(self, provider_id: UUID):
        """Update the information of an existing custom API tool provider"""
        req = UpdateApiToolProviderReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.api_tool_service.update_api_tool_provider(provider_id, req)

        return success_message("Custom API plugin updated successfully")

    def get_api_tool(self, provider_id: UUID, tool_name: str):
        """Get details of a specific tool by provider ID and tool name"""
        api_tool = self.api_tool_service.get_api_tool(provider_id, tool_name)

        resp = GetApiToolResp()

        return success_json(resp.dump(api_tool))

    def get_api_tool_provider(self, provider_id: UUID):
        """Get raw information of a tool provider by provider ID"""
        api_tool_provider = self.api_tool_service.get_api_tool_provider(provider_id)

        resp = GetApiToolProviderResp()

        return success_json(resp.dump(api_tool_provider))

    def delete_api_tool_provider(self, provider_id: UUID):
        """Delete a tool provider by provider ID"""
        self.api_tool_service.delete_api_tool_provider(provider_id)

        return success_message("Custom API plugin deleted successfully")

    def validate_openapi_schema(self):
        """Validate whether the provided OpenAPI schema string is correct"""
        req = ValidateOpenAPISchemaReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.api_tool_service.parse_openapi_schema(req.openapi_schema.data)

        return success_message("Schema validation successful")
