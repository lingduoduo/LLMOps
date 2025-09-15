#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : redis_extension.py
"""
import redis
from flask import Flask
from redis.connection import Connection, SSLConnection

# Redis client
redis_client = redis.Redis()


def init_app(app: Flask):
    """Initialize the Redis client"""
    # 1) Choose connection type based on environment (SSL vs non-SSL)
    connection_class = Connection
    if app.config.get("REDIS_USE_SSL", False):
        connection_class = SSLConnection

    # 2) Create the Redis connection pool
    redis_client.connection_pool = redis.ConnectionPool(
        **{
            "host": app.config.get("REDIS_HOST", "localhost"),
            "port": app.config.get("REDIS_PORT", 6379),
            "username": app.config.get("REDIS_USERNAME", None),
            "password": app.config.get("REDIS_PASSWORD", None),
            "db": app.config.get("REDIS_DB", 0),
            "encoding": "utf-8",
            "encoding_errors": "strict",
            "decode_responses": False,
        },
        connection_class=connection_class,
    )

    app.extensions["redis"] = redis_client
