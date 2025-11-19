#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : api_tool_schema.py
"""

from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField, ValidationError
from wtforms.validators import DataRequired, Length, URL, Optional

from internal.model import ApiToolProvider, ApiTool
from pkg.paginator import PaginatorReq
from .schema import ListField


class ValidateOpenAPISchemaReq(FlaskForm):
    """
    Request schema for validating OpenAPI-compliant JSON strings.
    """
    openapi_schema = StringField("openapi_schema", validators=[
        DataRequired(message="openapi_schema string cannot be empty")
    ])


class GetApiToolProvidersWithPageReq(PaginatorReq):
    """
    Request schema for getting a paginated list of API tool providers.
    """
    search_word = StringField("search_word", validators=[
        Optional()
    ])


class CreateApiToolReq(FlaskForm):
    """
    Request schema for creating a custom API tool provider.
    """
    name = StringField("name", validators=[
        DataRequired(message="Provider name cannot be empty"),
        Length(min=1, max=30, message="Provider name length must be between 1 and 30"),
    ])
    icon = StringField("icon", validators=[
        DataRequired(message="Provider icon cannot be empty"),
        URL(message="Provider icon must be a valid URL"),
    ])
    openapi_schema = StringField("openapi_schema", validators=[
        DataRequired(message="openapi_schema string cannot be empty")
    ])
    headers = ListField("headers", default=[])

    @classmethod
    def validate_headers(cls, form, field):
        """
        Validate that headers is a list of dictionaries with exactly 'key' and 'value' keys.
        """
        for header in field.data:
            if not isinstance(header, dict):
                raise ValidationError("Each item in headers must be a dictionary")
            if set(header.keys()) != {"key", "value"}:
                raise ValidationError("Each header dictionary must contain exactly 'key' and 'value' fields")


class UpdateApiToolProviderReq(FlaskForm):
    """
    Request schema for updating an API tool provider.
    """
    name = StringField("name", validators=[
        DataRequired(message="Provider name cannot be empty"),
        Length(min=1, max=30, message="Provider name length must be between 1 and 30"),
    ])
    icon = StringField("icon", validators=[
        DataRequired(message="Provider icon cannot be empty"),
        URL(message="Provider icon must be a valid URL"),
    ])
    openapi_schema = StringField("openapi_schema", validators=[
        DataRequired(message="openapi_schema string cannot be empty")
    ])
    headers = ListField("headers", default=[])

    @classmethod
    def validate_headers(cls, form, field):
        """
        Validate that headers is a list of dictionaries with exactly 'key' and 'value' keys.
        """
        for header in field.data:
            if not isinstance(header, dict):
                raise ValidationError("Each item in headers must be a dictionary")
            if set(header.keys()) != {"key", "value"}:
                raise ValidationError("Each header dictionary must contain exactly 'key' and 'value' fields")


class GetApiToolProviderResp(Schema):
    """
    Response schema for returning details of an API tool provider.
    """
    id = fields.UUID()
    name = fields.String()
    icon = fields.String()
    openapi_schema = fields.String()
    headers = fields.List(fields.Dict, default=[])
    created_at = fields.Integer(default=0)

    @pre_dump
    def process_data(self, data: ApiToolProvider, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "openapi_schema": data.openapi_schema,
            "headers": data.headers,
            "created_at": int(data.created_at.timestamp()),
        }


class GetApiToolResp(Schema):
    """
    Response schema for returning details of an API tool and its parameters.
    """
    id = fields.UUID()
    name = fields.String()
    description = fields.String()
    inputs = fields.List(fields.Dict, default=[])
    provider = fields.Dict()

    @pre_dump
    def process_data(self, data: ApiTool, **kwargs):
        provider = data.provider
        return {
            "id": data.id,
            "name": data.name,
            "description": data.description,
            "inputs": [
                {k: v for k, v in parameter.items() if k != "in"}
                for parameter in data.parameters
            ],
            "provider": {
                "id": provider.id,
                "name": provider.name,
                "icon": provider.icon,
                "description": provider.description,
                "headers": provider.headers,
            }
        }


class GetApiToolProvidersWithPageResp(Schema):
    """
    Response schema for returning a paginated list of API tool providers with their tools.
    """
    id = fields.UUID()
    name = fields.String()
    icon = fields.String()
    description = fields.String()
    headers = fields.List(fields.Dict, default=[])
    tools = fields.List(fields.Dict, default=[])
    created_at = fields.Integer(default=0)

    @pre_dump
    def process_data(self, data: ApiToolProvider, **kwargs):
        tools = data.tools
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "headers": data.headers,
            "tools": [
                {
                    "id": tool.id,
                    "description": tool.description,
                    "name": tool.name,
                    "inputs": [
                        {k: v for k, v in parameter.items() if k != "in"}
                        for parameter in tool.parameters
                    ]
                } for tool in tools
            ],
            "created_at": int(data.created_at.timestamp())
        }
