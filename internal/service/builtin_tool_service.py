#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : builtin_tool_service.py
"""
import mimetypes
import os.path
from dataclasses import dataclass
from typing import Any

from flask import current_app
from injector import inject
from langchain_core.pydantic_v1 import BaseModel

from internal.core.tools.builtin_tools.categories import BuiltinCategoryManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.exception import NotFoundException


@inject
@dataclass
class BuiltinToolService:
    """Service for managing built-in tools"""
    builtin_provider_manager: BuiltinProviderManager
    builtin_category_manager: BuiltinCategoryManager

    def get_builtin_tools(self) -> list:
        """Retrieve information about all built-in providers and their associated tools"""
        # 1. Get all providers
        providers = self.builtin_provider_manager.get_providers()

        # 2. Iterate through providers and extract tool information
        builtin_tools = []
        for provider in providers:
            provider_entity = provider.provider_entity
            tool_info = {
                **provider_entity.model_dump(exclude=["icon"]),
                "tools": [],
            }

            # 3. Loop through and extract all tool entities of the provider
            for tool_entity in provider.get_tool_entities():
                # 4. Get the tool function from the provider
                tool = provider.get_tool(tool_entity.name)

                # 5. Build tool entity information
                tool_dict = {
                    **tool_entity.model_dump(),
                    "inputs": self.get_tool_inputs(tool),
                }
                tool_info["tools"].append(tool_dict)

            builtin_tools.append(tool_info)

        return builtin_tools

    def get_provider_tool(self, provider_name: str, tool_name: str) -> dict:
        """Retrieve specific tool information by provider name and tool name"""
        # 1. Get the specified provider
        provider = self.builtin_provider_manager.get_provider(provider_name)
        if provider is None:
            raise NotFoundException(f"Provider '{provider_name}' not found")

        # 2. Get the specified tool entity from that provider
        tool_entity = provider.get_tool_entity(tool_name)
        if tool_entity is None:
            raise NotFoundException(f"Tool '{tool_name}' not found")

        # 3. Assemble provider and tool details
        provider_entity = provider.provider_entity
        tool = provider.get_tool(tool_name)

        builtin_tool = {
            "provider": {**provider_entity.model_dump(exclude=["icon", "created_at"])},
            **tool_entity.model_dump(),
            "created_at": provider_entity.created_at,
            "inputs": self.get_tool_inputs(tool),
        }
        return builtin_tool

    def get_provider_icon(self, provider_name: str) -> tuple[bytes, str]:
        """Get the icon image stream and its MIME type for the specified provider"""
        # 1. Find the provider
        provider = self.builtin_provider_manager.get_provider(provider_name)
        if not provider:
            raise NotFoundException(f"Provider '{provider_name}' not found")

        # 2. Determine the project root path
        root_path = os.path.dirname(os.path.dirname(current_app.root_path))

        # 3. Build path to the provider's directory
        provider_path = os.path.join(
            root_path,
            "internal", "core", "tools", "builtin_tools", "providers", provider_name,
        )

        # 4. Build path to the icon file
        icon_path = os.path.join(provider_path, "_asset", provider.provider_entity.icon)

        # 5. Check that the icon exists
        if not os.path.exists(icon_path):
            raise NotFoundException("No icon found in the provider's _asset directory")

        # 6. Determine the MIME type
        mimetype, _ = mimetypes.guess_type(icon_path)
        mimetype = mimetype or "application/octet-stream"

        # 7. Read and return the icon bytes
        with open(icon_path, "rb") as f:
            return f.read(), mimetype

    def get_categories(self) -> list[dict[str, Any]]:
        """Retrieve all built-in category information, including name, category, and icon"""
        category_map = self.builtin_category_manager.get_category_map()
        return [
            {
                "name": entry["entity"].name,
                "category": entry["entity"].category,
                "icon": entry["icon"],
            }
            for entry in category_map.values()
        ]

    @classmethod
    def get_tool_inputs(cls, tool) -> list[dict[str, Any]]:
        """Extract input parameter information from the given tool"""
        inputs = []
        if hasattr(tool, "args_schema") and issubclass(tool.args_schema, BaseModel):
            fields = getattr(tool.args_schema, "__fields__", None) \
                     or getattr(tool.args_schema, "model_fields", {})
            for field_name, model_field in fields.items():
                inputs.append({
                    "name": field_name,
                    "description": model_field.field_info.description or "",
                    "required": model_field.required,
                    "type": model_field.outer_type_.__name__,
                })
        return inputs
