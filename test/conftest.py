#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : conftest.py
"""
import os

import pytest
from sqlalchemy.orm import sessionmaker, scoped_session

from app.http.app import app as _app
from internal.extension.database_extension import db as _db


@pytest.fixture
def app():
    """Get and return the Flask application"""
    _app.config["TESTING"] = True
    return _app


@pytest.fixture
def client(app):
    """Get the Flask test client and return it"""
    with app.test_client() as client:
        access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0NmRiMzBkMS0zMTk5LTRlNzktYTBjZC1hYmYxMmZhNjg1OGYiLCJpc3MiOiJsbG1vcHMiLCJleHAiOjE3NjUyNDMyODV9.DnB_R9sL913JUCs9AYdo8Sv8jdBI0N0cbyimlv_FZPo"
        client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"
        yield client


@pytest.fixture
def db(app):
    """
    Create a temporary database session.
    When the test ends, roll back the entire transaction
    to isolate tests from the actual database.
    """
    with app.app_context():
        # 1. Get a database connection and begin a transaction
        connection = _db.engine.connect()
        transaction = connection.begin()

        # 2. Create a temporary database session
        session_factory = sessionmaker(bind=connection)
        session = scoped_session(session_factory)
        _db.session = session

        # 3. Provide the database instance
        yield _db

        # 4. Roll back the transaction, close the connection, and remove the session
        transaction.rollback()
        connection.close()
        session.remove()


@pytest.fixture(autouse=True, scope="session")
def _force_redis_url():
    os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/0"
