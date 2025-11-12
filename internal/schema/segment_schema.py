#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : segment_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField, BooleanField
from wtforms.validators import Optional, ValidationError, DataRequired

from internal.lib.helper import datetime_to_timestamp
from internal.model import Segment
from pkg.paginator import PaginatorReq
from .schema import ListField


class GetSegmentsWithPageReq(PaginatorReq):
    """Request to get a paginated list of document segments"""
    search_word = StringField("search_word", default="", validators=[Optional()])


class GetSegmentsWithPageResp(Schema):
    """Response schema for a paginated list of document segments"""
    id = fields.UUID(dump_default="")
    document_id = fields.UUID(dump_default="")
    dataset_id = fields.UUID(dump_default="")
    position = fields.Integer(dump_default=0)
    content = fields.String(dump_default="")
    keywords = fields.List(fields.String, dump_default=[])
    character_count = fields.Integer(dump_default=0)
    token_count = fields.Integer(dump_default=0)
    hit_count = fields.Integer(dump_default=0)
    enabled = fields.Boolean(dump_default=False)
    disabled_at = fields.Integer(dump_default=0)
    status = fields.String(dump_default="")
    error = fields.String(dump_default="")
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Segment, **kwargs):
        return {
            "id": data.id,
            "document_id": data.document_id,
            "dataset_id": data.dataset_id,
            "position": data.position,
            "content": data.content,
            "keywords": data.keywords,
            "character_count": data.character_count,
            "token_count": data.token_count,
            "hit_count": data.hit_count,
            "enabled": data.enabled,
            "disabled_at": datetime_to_timestamp(data.disabled_at),
            "status": data.status,
            "error": data.error,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }


class GetSegmentResp(Schema):
    """Response schema for document segment details"""
    id = fields.UUID(dump_default="")
    document_id = fields.UUID(dump_default="")
    dataset_id = fields.UUID(dump_default="")
    position = fields.Integer(dump_default=0)
    content = fields.String(dump_default="")
    keywords = fields.List(fields.String, dump_default=[])
    character_count = fields.Integer(dump_default=0)
    token_count = fields.Integer(dump_default=0)
    hit_count = fields.Integer(dump_default=0)
    hash = fields.String(dump_default="")
    enabled = fields.Boolean(dump_default=False)
    disabled_at = fields.Integer(dump_default=0)
    status = fields.String(dump_default="")
    error = fields.String(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Segment, **kwargs):
        return {
            "id": data.id,
            "document_id": data.document_id,
            "dataset_id": data.dataset_id,
            "position": data.position,
            "content": data.content,
            "keywords": data.keywords,
            "character_count": data.character_count,
            "token_count": data.token_count,
            "hit_count": data.hit_count,
            "hash": data.hash,
            "enabled": data.enabled,
            "disabled_at": datetime_to_timestamp(data.disabled_at),
            "status": data.status,
            "error": data.error,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }


class UpdateSegmentEnabledReq(FlaskForm):
    """Request to update the enabled status of a document segment"""
    enabled = BooleanField("enabled")

    def validate_enabled(self, field: BooleanField) -> None:
        """Validate the 'enabled' status"""
        if not isinstance(field.data, bool):
            raise ValidationError("The 'enabled' field cannot be empty and must be a boolean.")


class CreateSegmentReq(FlaskForm):
    """Request schema to create a document segment"""
    content = StringField("content", validators=[
        DataRequired("Segment content cannot be empty.")
    ])
    keywords = ListField("keywords")

    def validate_keywords(self, field: ListField) -> None:
        """Validate keyword list: must not be None; defaults to empty list"""
        # 1) Validate type + non-null
        if field.data is None:
            field.data = []
        if not isinstance(field.data, list):
            raise ValidationError("The keywords must be provided as an array.")

        # 2) Validate length: no more than 10 keywords
        if len(field.data) > 10:
            raise ValidationError("The number of keywords must be between 0 and 10.")

        # 3) Validate each keyword is a string
        for keyword in field.data:
            if not isinstance(keyword, str):
                raise ValidationError("Each keyword must be a string.")

        # 4) Remove duplicates and update
        field.data = list(dict.fromkeys(field.data))


class UpdateSegmentReq(FlaskForm):
    """Request to update a document segment"""
    content = StringField("content", validators=[
        DataRequired("Segment content cannot be empty.")
    ])
    keywords = ListField("keywords")

    def validate_keywords(self, field: ListField) -> None:
        """Validate keyword list: must not be None; defaults to empty list"""
        # 1) Validate type + non-null
        if field.data is None:
            field.data = []
        if not isinstance(field.data, list):
            raise ValidationError("The keywords must be provided as an array.")

        # 2) Validate length: no more than 10 keywords
        if len(field.data) > 10:
            raise ValidationError("The number of keywords must be between 0 and 10.")

        # 3) Validate each keyword is a string
        for keyword in field.data:
            if not isinstance(keyword, str):
                raise ValidationError("Each keyword must be a string.")

        # 4) Remove duplicates and update
        field.data = list(dict.fromkeys(field.data))
