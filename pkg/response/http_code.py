#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : http_code.py
"""
from enum import Enum


class HttpCode(str, Enum):
    """Basic HTTP business status codes"""
    SUCCESS = "success"  # Success status
    FAIL = "fail"  # Failure status
    NOT_FOUND = "not_found"  # Not found
    UNAUTHORIZED = "unauthorized"  # Unauthorized
    FORBIDDEN = "forbidden"  # Forbidden
    VALIDATE_ERROR = "validate_error"  # Data validation error
