#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : test_api_tool_handler.py
"""

import pytest

from pkg.response import HttpCode

openapi_schema_string = """{"server": "https://baidu.com", 
"description": "123", 
"paths": {"/location": {"get": {"description": "Get local location", 
"operationId":"xxx", 
"parameters":[{"name":"location", 
"in":"query", 
"description":"Parameter description", 
"required":true, "type":"str"}]}}}}"""


class TestApiToolHandler:
    """Test class for custom API plugin handler"""

    @pytest.mark.parametrize("openapi_schema", ["123", openapi_schema_string])
    def test_validate_openapi_schema(self, openapi_schema, client):
        resp = client.post("/api-tools/validate-openapi-schema",
                           json={"openapi_schema": openapi_schema})
        assert resp.status_code == 200
        if openapi_schema == "123":
            assert resp.json.get("code") == HttpCode.VALIDATE_ERROR
        elif openapi_schema == openapi_schema_string:
            assert resp.json.get("code") == HttpCode.SUCCESS

    @pytest.mark.parametrize("query", [
        {},
        {"current_page": 2},
        {"search_word": "Gaode"},
        {"search_word": "Ling Toolkit"},
    ])
    def test_get_api_tool_providers_with_page(self, query, client):
        resp = client.get("/api-tools", query_string=query)
        assert resp.status_code == 200
        if query.get("current_page") == 2:
            assert len(resp.json.get("data").get("list")) == 0
        elif query.get("search_word") == "Gaode":
            assert len(resp.json.get("data").get("list")) == 2
        elif query.get("search_word") == "Ling Toolkit":
            assert len(resp.json.get("data").get("list")) == 0
        else:
            assert resp.json.get("code") == HttpCode.SUCCESS

    @pytest.mark.parametrize("provider_id", [
        "a4b99b28-dcca-452d-b7ae-86f3188ca9cb",
        "a4b99b28-dcca-452d-b7ae-86f3188ca9cc"
    ])
    def test_get_api_tool_provider(self, provider_id, client):
        resp = client.get(f"/api-tools/{provider_id}")
        assert resp.status_code == 200
        if provider_id.endswith("4"):
            assert resp.json.get("code") == HttpCode.SUCCESS
        elif provider_id.endswith("5"):
            assert resp.json.get("code") == HttpCode.NOT_FOUND

    @pytest.mark.parametrize("provider_id, tool_name", [
        ("a4b99b28-dcca-452d-b7ae-86f3188ca9cb", "GetCurrentIp"),
        ("a4b99b28-dcca-452d-b7ae-86f3188ca9cb", "Ling")
    ])
    def test_get_api_tool(self, provider_id, tool_name, client):
        resp = client.get(f"/api-tools/{provider_id}/tools/{tool_name}")
        assert resp.status_code == 200
        if tool_name == "GetCurrentIp":
            assert resp.json.get("code") == HttpCode.SUCCESS
        elif tool_name == "Ling":
            assert resp.json.get("code") == HttpCode.NOT_FOUND

    def test_create_api_tool_provider(self, client, db):
        data = {
            "name": "Ling Learning Toolkit",
            "icon": "https://cdn.test.com/icon.png",
            "openapi_schema": "{\"description\":\"Query IP location, weather forecast, route planning, etc. via Gaode toolkit\",\"server\":\"https://gaode.example.com\",\"paths\":{\"/weather\":{\"get\":{\"description\":\"Get weather forecast for a specified city, e.g., Guangzhou\",\"operationId\":\"GetCurrentWeather\",\"parameters\":[{\"name\":\"location\",\"in\":\"query\",\"description\":\"City name to query weather for\",\"required\":true,\"type\":\"str\"}]}},\"/ip\":{\"post\":{\"description\":\"Query IP location based on given IP\",\"operationId\":\"GetCurrentIp\",\"parameters\":[{\"name\":\"ip\",\"in\":\"request_body\",\"description\":\"Standard IP address to query, e.g., 201.52.14.23\",\"required\":true,\"type\":\"str\"}]}}}}",
            "headers": [{"key": "Authorization", "value": "Bearer access_token"}]
        }
        resp = client.post("/api-tools", json=data)
        assert resp.status_code == 200

        from internal.model import ApiToolProvider
        api_tool_provider = db.session.query(ApiToolProvider).filter_by(name="Ling Learning Toolkit").one_or_none()
        assert api_tool_provider is not None

    def test_update_api_tool_provider(self, client, db):
        provider_id = "ed3d0910-93d9-4cfe-95a0-f29c09c02974"
        data = {
            "name": "test_update_api_tool_provider",
            "icon": "https://cdn.test.com/icon.png",
            "openapi_schema": "{\"description\":\"Query IP location, weather forecast, route planning, etc. via Gaode toolkit\",\"server\":\"https://gaode.example.com\",\"paths\":{\"/weather\":{\"get\":{\"description\":\"Get weather forecast for a specified city, e.g., Guangzhou\",\"operationId\":\"GetCurrentWeather\",\"parameters\":[{\"name\":\"location\",\"in\":\"query\",\"description\":\"City name to query weather for\",\"required\":true,\"type\":\"str\"}]}},\"/ip\":{\"post\":{\"description\":\"Query IP location based on given IP\",\"operationId\":\"GetLocationForIp\",\"parameters\":[{\"name\":\"ip\",\"in\":\"request_body\",\"description\":\"Standard IP address to query, e.g., 201.52.14.23\",\"required\":true,\"type\":\"str\"}]}}}}",
            "headers": [{"key": "Authorization", "value": "Bearer access_token"}]
        }
        resp = client.post(f"/api-tools/{provider_id}", json=data)
        assert resp.status_code == 200

        from internal.model import ApiToolProvider
        api_tool_provider = db.session.query(ApiToolProvider).get(provider_id)
        assert api_tool_provider.name == data.get("name")

    def test_delete_api_tool_provider(self, client, db):
        provider_id = "ed3d0910-93d9-4cfe-95a0-f29c09c02974"
        resp = client.post(f"/api-tools/{provider_id}/delete")
        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS

        from internal.model import ApiToolProvider
        api_tool_provider = db.session.query(ApiToolProvider).get(provider_id)
        assert api_tool_provider is None
