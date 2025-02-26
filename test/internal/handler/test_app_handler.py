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
    def test_completion(self, query, client):
        resp = client.post("/app/completion", json={"query": query})
        assert resp.status_code == 200
        if query is None:
            assert resp.json.get("code") == HttpCode.VALIDATE_ERROR
        else:
            assert resp.json.get("code") == HttpCode.SUCCESS
        print("resp", resp.json)
