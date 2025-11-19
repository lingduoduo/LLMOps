#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : auth_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields
from wtforms import StringField
from wtforms.validators import DataRequired, Email, Length, regexp

from pkg.password import password_pattern


class PasswordLoginReq(FlaskForm):
    """Request schema for account password login"""
    email = StringField("email", validators=[
        DataRequired("Login email cannot be empty"),
        Email("Invalid email format"),
        Length(min=5, max=254, message="Email length must be between 5 and 254 characters"),
    ])
    password = StringField("password", validators=[
        DataRequired("Password cannot be empty"),
        regexp(regex=password_pattern,
               message="Password must contain at least one letter, one number, and be 8–16 characters long"),
    ])


class PasswordLoginResp(Schema):
    """Response schema for account password authentication"""
    access_token = fields.String()
    expire_at = fields.Integer()
