#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : default_config.py
"""

# Default application configuration
DEFAULT_CONFIG = {
    # WTF configuration
    "WTF_CSRF_ENABLED": "False",

    # SQLAlchemy database configuration
    "SQLALCHEMY_DATABASE_URI": "",
    "SQLALCHEMY_POOL_SIZE": 30,
    "SQLALCHEMY_POOL_RECYCLE": 3600,
    "SQLALCHEMY_ECHO": "True",
}
