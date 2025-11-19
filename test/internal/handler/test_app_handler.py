#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : test_app_handler.py
"""
import pytest

from pkg.response import HttpCode


class TestAppHandler:
    """Test class for the app controller"""

    @pytest.mark.parametrize("query", [None, "Hello, who are you?"])
    def test_completion(self, client, query):
        resp = client.post("/app/completion", json={"query": query})
        assert resp.status_code == 200
        if query is None:
            assert resp.json.get("code") == HttpCode.VALIDATE_ERROR
        else:
            assert resp.json.get("code") == HttpCode.SUCCESS

    # @pytest.mark.parametrize(
    #     "app_id, query",
    #     [
    #         ("e0d13c78-870b-46df-b2f5-693ae9d5d727", None),
    #         ("fadb32bf-2db0-4469-ae12-183ff077faa6", "Hello, who are you?")
    #     ]
    # )
    # def test_completion(self, app_id, query, client):
    #     resp = client.post(f"/apps/{app_id}/debug", json={"query": query})
    #     assert resp.status_code == 200
    #     if query is None:
    #         assert resp.json.get("code") == HttpCode.VALIDATE_ERROR
    #     else:
    #         assert resp.json.get("code") == HttpCode.SUCCESS
