#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : redis_extension.py
"""
import os

import dotenv
import redis
from flask import Flask
from redis.connection import Connection, SSLConnection

# Redis client

dotenv.load_dotenv()
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

# redis_client = redis.Redis()
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
    ssl_cert_reqs="none",
    ssl=True
)


# print(redis_client.ping())


def init_app(app: Flask):
    """Initialize the Redis client"""
    # 1) Choose connection type based on environment (SSL vs non-SSL)
    connection_class = Connection
    if app.config.get("REDIS_USE_SSL", False):
        connection_class = SSLConnection

    # 2) Create the Redis connection pool
    redis_client.connection_pool = redis.ConnectionPool(
        **{
            "host": app.config.get("REDIS_HOST", REDIS_HOST),
            "port": app.config.get("REDIS_PORT", REDIS_PORT),
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
