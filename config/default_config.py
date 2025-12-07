#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : default_config.py
"""
# Default application settings
DEFAULT_CONFIG = {
    # WTForms config
    "WTF_CSRF_ENABLED": "False",

    # SQLAlchemy database configuration
    "SQLALCHEMY_DATABASE_URI": "",
    "SQLALCHEMY_POOL_SIZE": 30,
    "SQLALCHEMY_POOL_RECYCLE": 3600,
    "SQLALCHEMY_ECHO": "True",

    # Redis database configuration
    "REDIS_HOST": "localhost",
    "REDIS_PORT": 6379,
    "REDIS_USERNAME": "",
    "REDIS_PASSWORD": "",
    "REDIS_DB": 0,
    "REDIS_USE_SSL": "False",

    # Default Celery configuration
    "CELERY_BROKER_DB": 1,
    "CELERY_RESULT_BACKEND_DB": 1,
    "CELERY_TASK_IGNORE_RESULT": "False",
    "CELERY_RESULT_EXPIRES": 3600,
    "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP": "True",

    # Default Assistant Agent ID
    "ASSISTANT_AGENT_ID": "572fa89a-38ee-486b-8632-0e3c72b3eef5"
}
