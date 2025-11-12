#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : dataset_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField, IntegerField, FloatField
from wtforms.validators import (
    DataRequired,
    Length,
    URL,
    Optional,
    AnyOf, NumberRange,
)

from internal.entity.dataset_entity import RetrievalStrategy
from internal.lib.helper import datetime_to_timestamp
from internal.model import Dataset, DatasetQuery
from pkg.paginator import PaginatorReq


class CreateDatasetReq(FlaskForm):
    """Create dataset request"""
    name = StringField("name", validators=[
        DataRequired("Dataset name cannot be empty"),
        Length(max=100, message="Dataset name cannot exceed 100 characters"),
    ])
    icon = StringField("icon", validators=[
        DataRequired("Dataset icon cannot be empty"),
        URL("Dataset icon must be an image URL"),
    ])
    description = StringField("description", default="", validators=[
        Optional(),
        Length(max=2000, message="Description cannot exceed 2000 characters")
    ])


class GetDatasetResp(Schema):
    """Get dataset details response schema"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    document_count = fields.Integer(dump_default=0)
    hit_count = fields.Integer(dump_default=0)
    related_app_count = fields.Integer(dump_default=0)
    character_count = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Dataset, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "document_count": data.document_count,
            "hit_count": data.hit_count,
            "related_app_count": data.related_app_count,
            "character_count": data.character_count,
            "updated_at": int(data.updated_at.timestamp()),
            "created_at": int(data.created_at.timestamp()),
        }


class UpdateDatasetReq(FlaskForm):
    """Update dataset request"""
    name = StringField("name", validators=[
        DataRequired("Dataset name cannot be empty"),
        Length(max=100, message="Dataset name cannot exceed 100 characters"),
    ])
    icon = StringField("icon", validators=[
        DataRequired("Dataset icon cannot be empty"),
        URL("Dataset icon must be an image URL"),
    ])
    description = StringField("description", default="", validators=[
        Optional(),
        Length(max=2000, message="Description cannot exceed 2000 characters")
    ])


class GetDatasetsWithPageReq(PaginatorReq):
    """Get paginated datasets request"""
    search_word = StringField("search_word", default="", validators=[
        Optional(),
    ])


class GetDatasetsWithPageResp(Schema):
    """Get paginated datasets response"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    document_count = fields.Integer(dump_default=0)
    related_app_count = fields.Integer(dump_default=0)
    character_count = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Dataset, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "document_count": data.document_count,
            "related_app_count": data.related_app_count,
            "character_count": data.character_count,
            "updated_at": int(data.updated_at.timestamp()),
            "created_at": int(data.created_at.timestamp()),
        }


class HitReq(FlaskForm):
    """Dataset recall test request"""
    query = StringField("query", validators=[
        DataRequired("Query cannot be empty"),
        Length(max=200, message="Query length cannot exceed 200")
    ])
    retrieval_strategy = StringField("retrieval_strategy", validators=[
        DataRequired("Retrieval strategy cannot be empty"),
        AnyOf([item.value for item in RetrievalStrategy], message="Invalid retrieval strategy")
    ])
    k = IntegerField("k", validators=[
        DataRequired("K (max hits) cannot be empty"),
        NumberRange(min=1, max=10, message="K must be between 1 and 10")
    ])
    score = FloatField("score", validators=[
        NumberRange(min=0, max=0.99, message="Score threshold must be between 0 and 0.99")
    ])


class GetDatasetQueriesResp(Schema):
    """Get recent dataset queries response schema"""
    id = fields.UUID(dump_default="")
    dataset_id = fields.UUID(dump_default="")
    query = fields.String(dump_default="")
    source = fields.String(dump_default="")
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: DatasetQuery, **kwargs):
        return {
            "id": data.id,
            "dataset_id": data.dataset_id,
            "query": data.query,
            "source": data.source,
            "created_at": datetime_to_timestamp(data.created_at),
        }
