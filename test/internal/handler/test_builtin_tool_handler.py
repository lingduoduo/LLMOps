#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : test_builtin_tool_handler.py
"""
import pytest

from pkg.response import HttpCode


class TestBuiltinToolHandler:
    """Test class for the built-in tool handler"""

    def test_get_categories(self, client):
        """Test retrieving all category information"""
        resp = client.get("/builtin-tools/categories")
        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS
        assert len(resp.json.get("data")) > 0

    def test_get_builtin_tools(self, client):
        """Test retrieving all built-in tools"""
        resp = client.get("/builtin-tools")
        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS
        assert len(resp.json.get("data")) > 0

    @pytest.mark.parametrize(
        "provider_name, tool_name",
        [
            ("google", "google_serper"),
            ("ling", "ling_llmops"),
        ]
    )
    def test_get_provider_tool(self, provider_name, tool_name, client):
        """Test API for retrieving specific tool information"""
        resp = client.get(f"/builtin-tools/{provider_name}/tools/{tool_name}")
        assert resp.status_code == 200
        if provider_name == "google":
            assert resp.json.get("code") == HttpCode.SUCCESS
            assert resp.json.get("data").get("name") == tool_name
        elif provider_name == "ling":
            assert resp.json.get("code") == HttpCode.NOT_FOUND

    @pytest.mark.parametrize("provider_name", ["google", "ling"])
    def test_get_provider_icon(self, provider_name, client):
        """Test API for retrieving icon by provider name"""
        resp = client.get(f"/builtin-tools/{provider_name}/icon")
        assert resp.status_code == 200
        if provider_name == "ling":
            assert resp.json.get("code") == HttpCode.NOT_FOUND
