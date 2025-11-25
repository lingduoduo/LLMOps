#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : http_request_entity.py
"""
from enum import Enum

from langchain_core.pydantic_v1 import Field, validator, HttpUrl

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import (
    VariableEntity,
    VariableType,
    VariableValueType,
)
from internal.exception import ValidateErrorException


class HttpRequestMethod(str, Enum):
    """HTTP request method enum."""
    GET = "get"
    POST = "post"
    PUT = "put"
    PATCH = "patch"
    DELETE = "delete"
    HEAD = "head"
    OPTIONS = "options"


class HttpRequestInputType(str, Enum):
    """HTTP request input variable type."""
    PARAMS = "params"  # Query parameters
    HEADERS = "headers"  # HTTP headers
    BODY = "body"  # Request body


class HttpRequestNodeData(BaseNodeData):
    """HTTP request node data."""
    url: HttpUrl = ""  # Request URL
    method: HttpRequestMethod = HttpRequestMethod.GET  # HTTP method
    inputs: list[VariableEntity] = Field(default_factory=list)  # Input variable list
    outputs: list[VariableEntity] = Field(
        exclude=True,
        default_factory=lambda: [
            VariableEntity(
                name="status_code",
                type=VariableType.INT,
                value={"type": VariableValueType.GENERATED, "content": 0},
            ),
            VariableEntity(
                name="text",
                value={"type": VariableValueType.GENERATED},
            ),
        ],
    )

    @validator("inputs")
    def validate_inputs(cls, inputs: list[VariableEntity]):
        """Validate the HTTP request input variable list."""
        # 1. Validate that each input's meta["type"] is a valid HttpRequestInputType
        for input in inputs:
            if input.meta.get("type") not in HttpRequestInputType.__members__.values():
                raise ValidateErrorException("Invalid HTTP request parameter structure.")

        # 2. Return validated inputs
        return inputs
