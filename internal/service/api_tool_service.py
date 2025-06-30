#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : api_tool_service.py
"""

import json
from dataclasses import dataclass
from uuid import UUID

from injector import inject

from internal.core.tools.api_tools.entities import OpenAPISchema
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.exception import (
    ValidateErrorException,
    NotFoundException,
)
from internal.model import ApiToolProvider, ApiTool
from internal.schema.api_tool_schema import (
    CreateApiToolReq,
    # GetApiToolProvidersWithPageReq,
    UpdateApiToolProviderReq,
)
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


# from pkg.paginator import Paginator


@inject
@dataclass
class ApiToolService(BaseService):
    """Service for managing custom API plugins."""
    db: SQLAlchemy
    api_provider_manager: ApiProviderManager

    def update_api_tool_provider(self, provider_id: UUID, req: UpdateApiToolProviderReq):
        """Update API tool provider info based on provider_id and request."""
        # TODO: replace with real account_id once auth module is implemented
        account_id = "46db30d1-3199-4e79-a0cd-abf12fa6858f"

        # 1. Look up the provider by ID and verify ownership
        api_tool_provider = self.get(ApiToolProvider, provider_id)
        if api_tool_provider is None or str(api_tool_provider.account_id) != account_id:
            raise ValidateErrorException("Provider does not exist.")

        # 2. Validate the OpenAPI schema
        openapi_schema = self.parse_openapi_schema(req.openapi_schema.data)

        # 3. Ensure no other provider with the same name exists for this account
        check_api_tool_provider = self.db.session.query(ApiToolProvider).filter(
            ApiToolProvider.account_id == account_id,
            ApiToolProvider.name == req.name.data,
            ApiToolProvider.id != api_tool_provider.id,
        ).one_or_none()
        if check_api_tool_provider:
            raise ValidateErrorException(f"Provider name '{req.name.data}' already exists.")

        # 4. Start database transaction
        with self.db.auto_commit():
            # 5. Delete all tools under this provider
            self.db.session.query(ApiTool).filter(
                ApiTool.provider_id == api_tool_provider.id,
                ApiTool.account_id == account_id,
            ).delete()

        # 6. Update the provider record
        self.update(
            api_tool_provider,
            name=req.name.data,
            icon=req.icon.data,
            headers=req.headers.data,
            openapi_schema=req.openapi_schema.data,
        )

        # 7. Add new tools based on updated schema
        for path, path_item in openapi_schema.paths.items():
            for method, method_item in path_item.items():
                self.create(
                    ApiTool,
                    account_id=account_id,
                    provider_id=api_tool_provider.id,
                    name=method_item.get("operationId"),
                    description=method_item.get("description"),
                    url=f"{openapi_schema.server}{path}",
                    method=method,
                    parameters=method_item.get("parameters", []),
                )

    # def get_api_tool_providers_with_page(self, req: GetApiToolProvidersWithPageReq) -> tuple[list[Any], Paginator]:
    #     """Get paginated list of API tool providers for the account."""
    #     # TODO: replace with real account_id once auth module is implemented
    #     account_id = "46db30d1-3199-4e79-a0cd-abf12fa6858f"
    #
    #     # 1. Build paginator
    #     paginator = Paginator(db=self.db, req=req)
    #
    #     # 2. Build query filters
    #     filters = [ApiToolProvider.account_id == account_id]
    #     if req.search_word.data:
    #         filters.append(ApiToolProvider.name.ilike(f"%{req.search_word.data}%"))
    #
    #     # 3. Execute paginated query
    #     api_tool_providers = paginator.paginate(
    #         self.db.session.query(ApiToolProvider).filter(*filters).order_by(desc("created_at"))
    #     )
    #
    #     return api_tool_providers, paginator

    def get_api_tool(self, provider_id: UUID, tool_name: str) -> ApiTool:
        """Get details of a specific API tool by provider ID and tool name."""
        # TODO: replace with real account_id once auth module is implemented
        account_id = "46db30d1-3199-4e79-a0cd-abf12fa6858f"

        api_tool = self.db.session.query(ApiTool).filter_by(
            provider_id=provider_id,
            name=tool_name,
        ).one_or_none()

        if api_tool is None or str(api_tool.account_id) != account_id:
            raise NotFoundException("Tool does not exist.")

        return api_tool

    def get_api_tool_provider(self, provider_id: UUID) -> ApiToolProvider:
        """Get details of an API tool provider by provider ID."""
        # TODO: replace with real account_id once auth module is implemented
        account_id = "46db30d1-3199-4e79-a0cd-abf12fa6858f"

        # 1. Query provider by ID
        api_tool_provider = self.get(ApiToolProvider, provider_id)

        # 2. Verify ownership
        if api_tool_provider is None or str(api_tool_provider.account_id) != account_id:
            raise NotFoundException("Provider does not exist.")

        return api_tool_provider

    def create_api_tool(self, req: CreateApiToolReq) -> None:
        """Create a new API tool provider and its associated tools."""
        # TODO: replace with real account_id once auth module is implemented
        account_id = "46db30d1-3199-4e79-a0cd-abf12fa6858f"

        # 1. Validate and parse the OpenAPI schema
        openapi_schema = self.parse_openapi_schema(req.openapi_schema.data)

        # 2. Ensure provider name does not already exist for this account
        api_tool_provider = self.db.session.query(ApiToolProvider).filter_by(
            account_id=account_id,
            name=req.name.data,
        ).one_or_none()
        if api_tool_provider:
            raise ValidateErrorException(f"Provider name '{req.name.data}' already exists.")

        # 3. Create provider record
        api_tool_provider = self.create(
            ApiToolProvider,
            account_id=account_id,
            name=req.name.data,
            icon=req.icon.data,
            description=openapi_schema.description,
            openapi_schema=req.openapi_schema.data,
            headers=req.headers.data,
        )

        # 4. Create associated tools
        for path, path_item in openapi_schema.paths.items():
            for method, method_item in path_item.items():
                self.create(
                    ApiTool,
                    account_id=account_id,
                    provider_id=api_tool_provider.id,
                    name=method_item.get("operationId"),
                    description=method_item.get("description"),
                    url=f"{openapi_schema.server}{path}",
                    method=method,
                    parameters=method_item.get("parameters", []),
                )

    def delete_api_tool_provider(self, provider_id: UUID):
        """Delete an API tool provider and all its tools."""
        # TODO: replace with real account_id once auth module is implemented
        account_id = "46db30d1-3199-4e79-a0cd-abf12fa6858f"

        # 1. Verify provider exists and is owned by the account
        api_tool_provider = self.get(ApiToolProvider, provider_id)
        if api_tool_provider is None or str(api_tool_provider.account_id) != account_id:
            raise NotFoundException("Provider does not exist.")

        # 2. Start transaction
        with self.db.auto_commit():
            # 3. Delete all tools for this provider
            self.db.session.query(ApiTool).filter(
                ApiTool.provider_id == provider_id,
                ApiTool.account_id == account_id,
            ).delete()

            # 4. Delete provider
            self.db.session.delete(api_tool_provider)

    @classmethod
    def parse_openapi_schema(cls, openapi_schema_str: str) -> OpenAPISchema:
        """Parse the provided OpenAPI schema JSON string. Raise an error if invalid."""
        try:
            data = json.loads(openapi_schema_str.strip())
            if not isinstance(data, dict):
                raise
        except Exception as e:
            raise ValidateErrorException("Provided data must be a valid OpenAPI-compliant JSON string.")

        return OpenAPISchema(**data)

    def api_tool_invoke(self):
        """Example method to demonstrate invoking an API tool."""
        provider_id = "d72bb9d7-8794-4caf-bd60-1f992c537065"
        tool_name = "YoudaoSuggest"

        api_tool = self.db.session.query(ApiTool).filter(
            ApiTool.provider_id == provider_id,
            ApiTool.name == tool_name,
        ).one_or_none()
        api_tool_provider = api_tool.provider

        from internal.core.tools.api_tools.entities import ToolEntity
        tool = self.api_provider_manager.get_tool(ToolEntity(
            id=provider_id,
            name=tool_name,
            url=api_tool.url,
            method=api_tool.method,
            description=api_tool.description,
            headers=api_tool_provider.headers,
            parameters=api_tool.parameters,
        ))
        return tool.invoke({"q": "love", "doctype": "json"})
