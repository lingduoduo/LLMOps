#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : api_key_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import BooleanField, StringField
from wtforms.validators import Length

from internal.lib.helper import datetime_to_timestamp
from internal.model import ApiKey


class CreateApiKeyReq(FlaskForm):
    """Request to create an API key"""
    is_active = BooleanField("is_active")
    remark = StringField("remark", validators=[
        Length(max=100, message="Remark cannot exceed 100 characters")
    ])


class UpdateApiKeyReq(FlaskForm):
    """Request to update an API key"""
    is_active = BooleanField("is_active")
    remark = StringField("remark", validators=[
        Length(max=100, message="Remark cannot exceed 100 characters")
    ])


class UpdateApiKeyIsActiveReq(FlaskForm):
    """Request to update API key activation state"""
    is_active = BooleanField("is_active")


class GetApiKeysWithPageResp(Schema):
    """Paginated response schema for API key list"""
    id = fields.UUID(dump_default="")
    api_key = fields.String(dump_default="")
    is_active = fields.Boolean(dump_default=False)
    remark = fields.String(dump_default="")
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: ApiKey, **kwargs):
        return {
            "id": data.id,
            "api_key": data.api_key,
            "is_active": data.is_active,
            "remark": data.remark,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }
