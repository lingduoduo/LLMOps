#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : api_tool_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
# from pkg.paginator import PaginatorReq
from wtforms import StringField, ValidationError
from wtforms.validators import DataRequired, Length, URL

from internal.model import ApiToolProvider, ApiTool
from .schema import ListField


class ValidateOpenAPISchemaReq(FlaskForm):
    """Request for validating an OpenAPI schema string"""
    openapi_schema = StringField("openapi_schema", validators=[
        DataRequired(message="The openapi_schema string cannot be empty")
    ])


# class GetApiToolProvidersWithPageReq(PaginatorReq):
#     """Request for retrieving a paginated list of API tool providers"""
#     search_word = StringField("search_word", validators=[Optional()])


class CreateApiToolReq(FlaskForm):
    """Request to create a custom API tool provider"""
    name = StringField("name", validators=[
        DataRequired(message="Tool provider name cannot be empty"),
        Length(min=1, max=30, message="Tool provider name must be between 1 and 30 characters"),
    ])
    icon = StringField("icon", validators=[
        DataRequired(message="Tool provider icon cannot be empty"),
        URL(message="Tool provider icon must be a valid URL"),
    ])
    openapi_schema = StringField("openapi_schema", validators=[
        DataRequired(message="The openapi_schema string cannot be empty")
    ])

    headers = ListField("headers", default=[])

    @classmethod
    def validate_headers(cls, form, field):
        """Validate the headers field: must be a list of dictionaries with 'key' and 'value' keys only"""
        for header in field.data:
            if not isinstance(header, dict):
                raise ValidationError("Each element in headers must be a dictionary")
            if set(header.keys()) != {"key", "value"}:
                raise ValidationError("Each header must only contain 'key' and 'value' keys")


class UpdateApiToolProviderReq(FlaskForm):
    """Request to update an existing API tool provider"""
    name = StringField("name", validators=[
        DataRequired(message="Tool provider name cannot be empty"),
        Length(min=1, max=30, message="Tool provider name must be between 1 and 30 characters"),
    ])
    icon = StringField("icon", validators=[
        DataRequired(message="Tool provider icon cannot be empty"),
        URL(message="Tool provider icon must be a valid URL"),
    ])
    openapi_schema = StringField("openapi_schema", validators=[
        DataRequired(message="The openapi_schema string cannot be empty")
    ])

    headers = ListField("headers", default=[])

    @classmethod
    def validate_headers(cls, form, field):
        """Validate the headers field: must be a list of dictionaries with 'key' and 'value' keys only"""
        for header in field.data:
            if not isinstance(header, dict):
                raise ValidationError("Each element in headers must be a dictionary")
            if set(header.keys()) != {"key", "value"}:
                raise ValidationError("Each header must only contain 'key' and 'value' keys")


class GetApiToolProviderResp(Schema):
    """Response for getting API tool provider details"""
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
    """Response for getting details of a specific API tool"""
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
            "inputs": [{k: v for k, v in parameter.items() if k != "in"} for parameter in data.parameters],
            "provider": {
                "id": provider.id,
                "name": provider.name,
                "icon": provider.icon,
                "description": provider.description,
                "headers": provider.headers,
            }
        }
