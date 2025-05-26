#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : api_tool_service.py
"""

from dataclasses import dataclass
from uuid import UUID

from injector import inject

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
    """Service for managing custom API plugins"""
    db: SQLAlchemy
    api_provider_manager: ApiProviderManager

    def update_api_tool_provider(self, provider_id: UUID, req: UpdateApiToolProviderReq):
        """Update the API tool provider's information based on provider_id and request"""
        # TODO: Replace hardcoded account_id with auth module
        account_id = "46db30d1-3199-4e79-a0cd-abf12fa6858f"

        # 1. Retrieve and validate the provider
        api_tool_provider = self.get(ApiToolProvider, provider_id)
        if api_tool_provider is None or str(api_tool_provider.account_id) != account_id:
            raise ValidateErrorException("The tool provider does not exist.")

        # 2. Validate OpenAPI schema
        openapi_schema = self.parse_openapi_schema(req.openapi_schema.data)

        # 3. Check for duplicate provider names under the same account
        existing_provider = self.db.session.query(ApiToolProvider).filter(
            ApiToolProvider.account_id == account_id,
            ApiToolProvider.name == req.name.data,
            ApiToolProvider.id != api_tool_provider.id,
        ).one_or_none()
        if existing_provider:
            raise ValidateErrorException(f"The tool provider name '{req.name.data}' already exists.")

        # 4. Begin transaction
        with self.db.auto_commit():
            # 5. Delete all tools under the current provider
            self.db.session.query(ApiTool).filter(
                ApiTool.provider_id == api_tool_provider.id,
                ApiTool.account_id == account_id,
            ).delete()

        # 6. Update the tool provider
        self.update(
            api_tool_provider,
            name=req.name.data,
            icon=req.icon.data,
            headers=req.headers.data,
            openapi_schema=req.openapi_schema.data,
        )

        # 7. Add new tools based on the OpenAPI schema
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
    #     """Get a paginated list of API tool providers"""
    #     # TODO: Replace hardcoded account_id with auth module
    #     account_id = "46db30d1-3199-4e79-a0cd-abf12fa6858f"
    #
    #     paginator = Paginator(db=self.db, req=req)
    #
    #     filters = [ApiToolProvider.account_id == account_id]
    #     if req.search_word.data:
    #         filters.append(ApiToolProvider.name.ilike(f"%{req.search_word.data}%"))
    #
    #     providers = paginator.paginate(
    #         self.db.session.query(ApiToolProvider).filter(*filters).order_by(desc("created_at"))
    #     )
    #
    #     return providers, paginator

    def get_api_tool(self, provider_id: UUID, tool_name: str) -> ApiTool:
        """Get tool details based on provider_id and tool_name"""
        # TODO: Replace hardcoded account_id with auth module
        account_id = "46db30d1-3199-4e79-a0cd-abf12fa6858f"

        api_tool = self.db.session.query(ApiTool).filter_by(
            provider_id=provider_id,
            name=tool_name,
        ).one_or_none()

        if api_tool is None or str(api_tool.account_id) != account_id:
            raise NotFoundException("The tool does not exist.")

        return api_tool

    def get_api_tool_provider(self, provider_id: UUID) -> ApiToolProvider:
        """Get the provider's information based on provider_id"""
        # TODO: Replace hardcoded account_id with auth module
        account_id = "46db30d1-3199-4e79-a0cd-abf12fa6858f"

        provider = self.get(ApiToolProvider, provider_id)

        if provider is None or str(provider.account_id) != account_id:
            raise NotFoundException("The tool provider does not exist.")

        return provider

    def create_api_tool(self, req: CreateApiToolReq) -> None:
        """Create a new API tool provider and associated tools"""
        # TODO: Replace hardcoded account_id with auth module
        account_id = "46db30d1-3199-4e79-a0cd-abf12fa6858f"

        openapi_schema = self.parse_openapi_schema(req.openapi_schema.data)

        existing_provider = self.db.session.query(ApiToolProvider).filter_by(
            account_id=account_id,
            name=req.name.data,
        ).one_or_none()
        if existing_provider:
            raise ValidateErrorException(f"The tool provider name '{req.name.data}' already exists.")

        # Create provider
        api_tool_provider = self.create(
            ApiToolProvider,
            account_id=account_id,
            name=req.name.data,
            icon=req.icon.data,
            description=openapi_schema.description,
            openapi_schema=req.openapi_schema.data,
            headers=req.headers.data,
        )

        # Create tools
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
        """Delete a tool provider and all associated tools by provider_id"""
        # TODO:
