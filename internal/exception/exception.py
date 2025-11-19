#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : exception.py
"""
from dataclasses import field
from typing import Any

from pkg.response import HttpCode


class CustomException(Exception):
    """Base custom exception"""
    code: HttpCode = HttpCode.FAIL
    message: str = ""
    data: Any = field(default_factory=dict)

    def __init__(self, message: str = None, data: Any = None):
        super().__init__()
        self.message = message
        self.data = data


class FailException(CustomException):
    """General failure exception"""
    pass


class NotFoundException(CustomException):
    """Data not found exception"""
    code = HttpCode.NOT_FOUND


class UnauthorizedException(CustomException):
    """Unauthorized exception"""
    code = HttpCode.UNAUTHORIZED


class ForbiddenException(CustomException):
    """Permission denied exception"""
    code = HttpCode.FORBIDDEN


class ValidateErrorException(CustomException):
    """Data validation exception"""
    code = HttpCode.VALIDATE_ERROR
