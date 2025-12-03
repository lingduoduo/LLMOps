#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : builtin_app_schema.py
"""
from flask_wtf import FlaskForm
from internal.core.builtin_apps.entities.builtin_app_entity import BuiltinAppEntity
from internal.core.builtin_apps.entities.category_entity import CategoryEntity
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField
from wtforms.validators import DataRequired, UUID


class GetBuiltinAppCategoriesResp(Schema):
    """Response schema for built-in app category list"""
    category = fields.String(dump_default="")
    name = fields.String(dump_default="")

    @pre_dump
    def process_data(self, data: CategoryEntity, **kwargs):
        return data.model_dump()


class GetBuiltinAppsResp(Schema):
    """Response schema for list of built-in app entities"""
    id = fields.String(dump_default="")
    category = fields.String(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    model_config = fields.Dict(dump_default={})
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: BuiltinAppEntity, **kwargs):
        return {
            **data.model_dump(include={"id", "category", "name", "icon", "description", "created_at"}),
            "model_config": {
                "provider": data.language_model_config.get("provider", ""),
                "model": data.language_model_config.get("model", ""),
            }
        }


class AddBuiltinAppToSpaceReq(FlaskForm):
    """Request schema for adding a built-in app to a user's space"""
    builtin_app_id = StringField(
        "builtin_app_id",
        default="",
        validators=[
            DataRequired("Built-in app ID cannot be empty"),
            UUID("Built-in app ID must be a valid UUID"),
        ],
    )
