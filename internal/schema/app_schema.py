#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : app_schema.py
"""
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired, Length


class CompletionReq(FlaskForm):
    """Basic chat interface request validation"""
    # Required, maximum length of 2000
    query = StringField("query", validators=[
        DataRequired(message="User query is required"),
        Length(max=2000, message="User query must not exceed 2000 characters"),
    ])
