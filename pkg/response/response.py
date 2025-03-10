#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : response.py
"""
from dataclasses import field, dataclass
from typing import Any

from flask import jsonify

from .http_code import HttpCode


@dataclass
class Response:
    """Basic HTTP API response format"""
    code: HttpCode = HttpCode.SUCCESS
    message: str = ""
    data: Any = field(default_factory=dict)


def json(data: Response = None):
    """Basic response interface"""
    response = jsonify(data)
    # response.headers["Access-Control-Allow-Origin"] = "http://localhost:5173"
    # response.headers["Access-Control-Allow-Header"] = "Content-Type"
    # response.headers["Access-Control-Allow-Methods"] = "GET, POST"
    # response.headers["Access-Control-Allow-Credential"] = "true"
    return response, 200


def success_json(data: Any = None):
    """Successful data response"""
    return json(Response(code=HttpCode.SUCCESS, message="", data=data))


def fail_json(data: Any = None):
    """Failure data response"""
    return json(Response(code=HttpCode.FAIL, message="", data=data))


def validate_error_json(errors: dict = None):
    """Data validation error response"""
    first_key = next(iter(errors))
    if first_key is not None:
        msg = errors.get(first_key)[0]
    else:
        msg = ""
    return json(Response(code=HttpCode.VALIDATE_ERROR, message=msg, data=errors))


def message(code: HttpCode = None, msg: str = ""):
    """Basic message response, always returns a message prompt with an empty dictionary as data"""
    return json(Response(code=code, message=msg, data={}))


def success_message(msg: str = ""):
    """Success message response"""
    return message(code=HttpCode.SUCCESS, msg=msg)


def fail_message(msg: str = ""):
    """Failure message response"""
    return message(code=HttpCode.FAIL, msg=msg)


def not_found_message(msg: str = ""):
    """Not found message response"""
    return message(code=HttpCode.NOT_FOUND, msg=msg)


def unauthorized_message(msg: str = ""):
    """Unauthorized message response"""
    return message(code=HttpCode.UNAUTHORIZED, msg=msg)


def forbidden_message(msg: str = ""):
    """Forbidden message response"""
    return message(code=HttpCode.FORBIDDEN, msg=msg)
