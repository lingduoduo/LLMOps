#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : oauth_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields
from wtforms import StringField
from wtforms.validators import DataRequired


class AuthorizeReq(FlaskForm):
    """Request body for third-party OAuth authorization."""
    code = StringField("code", validators=[DataRequired("Authorization code cannot be empty")])


class AuthorizeResp(Schema):
    """Response structure for third-party OAuth authorization."""
    access_token = fields.String()
    expire_at = fields.Integer()
