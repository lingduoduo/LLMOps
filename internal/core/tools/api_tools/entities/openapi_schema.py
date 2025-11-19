#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : openapi_schema.py
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from internal.exception import ValidateErrorException


class ParameterType(str, Enum):
    """Supported parameter types"""
    STR: str = "str"
    INT: str = "int"
    FLOAT: str = "float"
    BOOL: str = "bool"


ParameterTypeMap = {
    ParameterType.STR: str,
    ParameterType.INT: int,
    ParameterType.FLOAT: float,
    ParameterType.BOOL: bool,
}


class ParameterIn(str, Enum):
    """Supported parameter locations"""
    PATH: str = "path"
    QUERY: str = "query"
    HEADER: str = "header"
    COOKIE: str = "cookie"
    REQUEST_BODY: str = "request_body"


class OpenAPISchema(BaseModel):
    """Data structure representing an OpenAPI schema"""
    server: str = Field(default="", validate_default=True, description="Base URL of the tool provider service")
    description: str = Field(default="", validate_default=True, description="Description of the tool provider")
    paths: dict[str, dict] = Field(default_factory=dict, validate_default=True, description="Path definitions")

    @field_validator("server", mode="before")
    def validate_server(cls, server: str) -> str:
        """Validate the 'server' field"""
        if server is None or server == "":
            raise ValidateErrorException("The 'server' field cannot be empty and must be a string")
        return server

    @field_validator("description", mode="before")
    def validate_description(cls, description: str) -> str:
        """Validate the 'description' field"""
        if description is None or description == "":
            raise ValidateErrorException("The 'description' field cannot be empty and must be a string")
        return description

    @field_validator("paths", mode="before")
    def validate_paths(cls, paths: dict[str, dict]) -> dict[str, dict]:
        """
        Validate the 'paths' field. Includes:
        - Method extraction
        - Ensuring unique 'operationId'
        - Validating 'parameters'
        """
        # 1. Ensure paths is a non-empty dictionary
        if not paths or not isinstance(paths, dict):
            raise ValidateErrorException("'paths' in openapi_schema must be a non-empty dictionary")

        methods = ["get", "post"]
        interfaces = []
        validated_paths = {}

        # 2. Extract valid HTTP methods from each path
        for path, path_item in paths.items():
            for method in methods:
                if method in path_item:
                    interfaces.append({
                        "path": path,
                        "method": method,
                        "operation": path_item[method],
                    })

        # 3. Validate each operation
        operation_ids = []
        for interface in interfaces:
            operation = interface["operation"]
            path = interface["path"]
            method = interface["method"]

            # 4. Validate required fields
            if not isinstance(operation.get("description"), str):
                raise ValidateErrorException("Each operation must have a non-empty 'description' string")
            if not isinstance(operation.get("operationId"), str):
                raise ValidateErrorException("Each operation must have a non-empty 'operationId' string")
            if not isinstance(operation.get("parameters", []), list):
                raise ValidateErrorException("'parameters' must be a list or omitted")

            # 5. Ensure operationId is unique
            if operation["operationId"] in operation_ids:
                raise ValidateErrorException(f"'operationId' must be unique. Duplicate: {operation['operationId']}")
            operation_ids.append(operation["operationId"])

            # 6. Validate each parameter
            for parameter in operation.get("parameters", []):
                if not isinstance(parameter.get("name"), str):
                    raise ValidateErrorException("parameter.name must be a non-empty string")
                if not isinstance(parameter.get("description"), str):
                    raise ValidateErrorException("parameter.description must be a non-empty string")
                if not isinstance(parameter.get("required"), bool):
                    raise ValidateErrorException("parameter.required must be a boolean")
                if (
                        not isinstance(parameter.get("in"), str)
                        or parameter.get("in") not in ParameterIn.__members__.values()
                ):
                    raise ValidateErrorException(
                        f"parameter.in must be one of: {'/'.join([item.value for item in ParameterIn])}"
                    )
                if (
                        not isinstance(parameter.get("type"), str)
                        or parameter.get("type") not in ParameterType.__members__.values()
                ):
                    raise ValidateErrorException(
                        f"parameter.type must be one of: {'/'.join([item.value for item in ParameterType])}"
                    )

            # 7. Build validated path entry
            validated_paths[path] = {
                method: {
                    "description": operation["description"],
                    "operationId": operation["operationId"],
                    "parameters": [{
                        "name": parameter.get("name"),
                        "in": parameter.get("in"),
                        "description": parameter.get("description"),
                        "required": parameter.get("required"),
                        "type": parameter.get("type"),
                    } for parameter in operation.get("parameters", [])]
                }
            }

        return validated_paths
