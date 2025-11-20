#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : openapi_schema.py
"""
import uuid

from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField
from wtforms.validators import DataRequired, UUID, Optional, ValidationError


class OpenAPIChatReq(FlaskForm):
    """Request schema for the OpenAPI Chat endpoint"""
    app_id = StringField("app_id", validators=[
        DataRequired("app_id cannot be empty"),
        UUID("app_id must be a valid UUID"),
    ])
    end_user_id = StringField("end_user_id", default="", validators=[
        Optional(),
        UUID("end_user_id must be a valid UUID"),
    ])
    conversation_id = StringField("conversation_id", default="")
    query = StringField("query", default="", validators=[
        DataRequired("query cannot be empty"),
    ])
    stream = BooleanField("stream", default=True)

    def validate_conversation_id(self, field: StringField) -> None:
        """Custom validator for conversation_id"""
        # 1. If provided, conversation_id must be a valid UUID
        if field.data:
            try:
                uuid.UUID(field.data)
            except Exception:
                raise ValidationError("conversation_id must be a valid UUID")

            # 2. end_user_id cannot be empty when conversation_id is provided
            if not self.end_user_id.data:
                raise ValidationError("end_user_id is required when conversation_id is provided")
