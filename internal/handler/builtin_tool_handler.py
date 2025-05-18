#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : builtin_tool_handler.py
"""
from dataclasses import dataclass

from injector import inject

from internal.service import BuiltinToolService
from pkg.response import success_json


@inject
@dataclass
class BuiltinToolHandler:
    """Handler for built-in tools"""

    builtin_tool_service: BuiltinToolService

    def get_builtin_tools(self):
        """Retrieve information for all built-in LLMOps tools along with provider details"""
        builtin_tools = self.builtin_tool_service.get_builtin_tools()
        return success_json(builtin_tools)

    def get_provider_tool(self, provider_name: str, tool_name: str):
        """Get information for a specific tool by provider name and tool name"""
        builtin_tool = self.builtin_tool_service.get_provider_tool(provider_name, tool_name)
        return success_json(builtin_tool)

    def get_provider_icon(self, provider_name: str):
        """Fetch the icon image stream for the specified provider"""
        # icon, mimetype = self.builtin_tool_service.get_provider_icon(provider_name)
        # return send_file(io.BytesIO(icon), mimetype)
        pass

    def get_categories(self):
        """Retrieve category information for all built-in providers"""
        # categories = self.builtin_tool_service.get_categories()
        # return success_json(categories)
        pass
