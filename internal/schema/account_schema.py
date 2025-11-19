#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : account_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField
from wtforms.validators import DataRequired, regexp, Length, URL

from internal.lib.helper import datetime_to_timestamp
from internal.model import Account
from pkg.password import password_pattern


class GetCurrentUserResp(Schema):
    """Response schema for retrieving current logged-in user information"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    email = fields.String(dump_default="")
    avatar = fields.String(dump_default="")
    last_login_at = fields.Integer(dump_default=0)
    last_login_ip = fields.String(dump_default="")
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Account, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "email": data.email,
            "avatar": data.avatar,
            "last_login_at": datetime_to_timestamp(data.last_login_at),
            "last_login_ip": data.last_login_ip,
            "created_at": datetime_to_timestamp(data.created_at),
        }


class UpdatePasswordReq(FlaskForm):
    """Request schema for updating account password"""
    password = StringField("password", validators=[
        DataRequired("Login password cannot be empty"),
        regexp(regex=password_pattern,
               message="Password must contain at least one letter, one number, and be 8–16 characters long"),
    ])


class UpdateNameReq(FlaskForm):
    """Request schema for updating account name"""
    name = StringField("name", validators=[
        DataRequired("Account name cannot be empty"),
        Length(min=3, max=30, message="Account name length must be between 3 and 30 characters"),
    ])


class UpdateAvatarReq(FlaskForm):
    """Request schema for updating account avatar"""
    avatar = StringField("avatar", validators=[
        DataRequired("Account avatar cannot be empty"),
        URL("Account avatar must be a valid image URL"),
    ])
