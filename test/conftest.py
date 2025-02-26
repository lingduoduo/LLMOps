#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : conftest.py
"""
import pytest

from app.http.app import app


@pytest.fixture
def client():
    """Retrieve the test client for the Flask application and return it"""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
