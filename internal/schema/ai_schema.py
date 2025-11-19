#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : ai_schema.py
"""
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired, UUID, Length


class GenerateSuggestedQuestionsReq(FlaskForm):
    """Request schema for generating a list of suggested questions"""
    message_id = StringField(
        "message_id",
        validators=[
            DataRequired("Message ID cannot be empty"),
            UUID(message="Message ID must be a valid UUID")
        ]
    )


class OptimizePromptReq(FlaskForm):
    """Request schema for optimizing a preset prompt"""
    prompt = StringField(
        "prompt",
        validators=[
            DataRequired("Preset prompt cannot be empty"),
            Length(max=2000, message="Preset prompt cannot exceed 2000 characters")
        ]
    )
