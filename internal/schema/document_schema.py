#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : document_schema.py
"""
import uuid

from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField, BooleanField
from wtforms.validators import DataRequired, AnyOf, ValidationError, Length, Optional

from internal.entity.dataset_entity import ProcessType, DEFAULT_PROCESS_RULE
from internal.lib.helper import datetime_to_timestamp
from internal.model import Document
from pkg.paginator import PaginatorReq
from .schema import ListField, DictField


class CreateDocumentsReq(FlaskForm):
    """Create/add documents request"""
    upload_file_ids = ListField("upload_file_ids")
    process_type = StringField("process_type", validators=[
        DataRequired("Document processing type cannot be empty"),
        AnyOf(values=[ProcessType.AUTOMATIC, ProcessType.CUSTOM], message="Invalid processing type")
    ])
    rule = DictField("rule")

    def validate_upload_file_ids(self, field: ListField) -> None:
        """Validate list of upload file IDs"""
        # 1) Type & non-empty check
        if not isinstance(field.data, list):
            raise ValidationError("File ID list must be an array")

        # 2) Length check: max 10 records
        if len(field.data) == 0 or len(field.data) > 10:
            raise ValidationError("Number of new documents must be within 0–10")

        # 3) Validate each ID is UUID
        for upload_file_id in field.data:
            try:
                uuid.UUID(upload_file_id)
            except Exception:
                raise ValidationError("Each file ID must be a UUID")

        # 4) De-duplicate
        field.data = list(dict.fromkeys(field.data))

    def validate_rule(self, field: DictField) -> None:
        """Validate processing rule"""
        # 1) If mode is AUTOMATIC, use default rule
        if self.process_type.data == ProcessType.AUTOMATIC:
            field.data = DEFAULT_PROCESS_RULE["rule"]
        else:
            # 2) In CUSTOM mode, rule must be provided
            if not isinstance(field.data, dict) or len(field.data) == 0:
                raise ValidationError("Rule cannot be empty in custom mode")

            # 3) Validate pre_process_rules exists and is a list
            if "pre_process_rules" not in field.data or not isinstance(field.data["pre_process_rules"], list):
                raise ValidationError("pre_process_rules must be a list")

            # 4) Keep only unique preprocess rules to avoid duplicates
            unique_pre_process_rule_dict = {}
            for pre_process_rule in field.data["pre_process_rules"]:
                # 5) Validate id: non-empty and one of allowed IDs
                if (
                        "id" not in pre_process_rule
                        or pre_process_rule["id"] not in ["remove_extra_space", "remove_url_and_email"]
                ):
                    raise ValidationError("Invalid preprocess rule id")

                # 6) Validate enabled: non-empty and boolean
                if "enabled" not in pre_process_rule or not isinstance(pre_process_rule["enabled"], bool):
                    raise ValidationError("Invalid preprocess rule enabled flag")

                # 7) Add to unique dict, filtering out unrelated data
                unique_pre_process_rule_dict[pre_process_rule["id"]] = {
                    "id": pre_process_rule["id"],
                    "enabled": pre_process_rule["enabled"],
                }

            # 8) Must have exactly two preprocess rules
            if len(unique_pre_process_rule_dict) != 2:
                raise ValidationError("Preprocess rules format error; please try again")

            # 9) Replace with de-duplicated list
            field.data["pre_process_rules"] = list(unique_pre_process_rule_dict.values())

            # 10) Validate segment: must exist and be a dict
            if "segment" not in field.data or not isinstance(field.data["segment"], dict):
                raise ValidationError("Segment settings must be a non-empty dict")

            # 11) Validate separators: must exist, be a list of strings, and non-empty
            if "separators" not in field.data["segment"] or not isinstance(field.data["segment"]["separators"], list):
                raise ValidationError("Separators must be a list and cannot be empty")
            for separator in field.data["segment"]["separators"]:
                if not isinstance(separator, str):
                    raise ValidationError("Each separator must be a string")
            if len(field.data["segment"]["separators"]) == 0:
                raise ValidationError("Separators list cannot be empty")

            # 12) Validate chunk_size: integer within range
            if "chunk_size" not in field.data["segment"] or not isinstance(field.data["segment"]["chunk_size"], int):
                raise ValidationError("chunk_size must be an integer and cannot be empty")
            if field.data["segment"]["chunk_size"] < 100 or field.data["segment"]["chunk_size"] > 1000:
                raise ValidationError("chunk_size must be within 100–1000")

            # 13) Validate chunk_overlap: integer within range (0 to 50% of chunk_size)
            if (
                    "chunk_overlap" not in field.data["segment"]
                    or not isinstance(field.data["segment"]["chunk_overlap"], int)
            ):
                raise ValidationError("chunk_overlap must be an integer and cannot be empty")
            if not (0 <= field.data["segment"]["chunk_overlap"] <= field.data["segment"]["chunk_size"] * 0.5):
                raise ValidationError(
                    f"chunk_overlap must be within 0–{int(field.data['segment']['chunk_size'] * 0.5)}"
                )

            # 14) Normalize and drop extraneous fields
            field.data = {
                "pre_process_rules": field.data["pre_process_rules"],
                "segment": {
                    "separators": field.data["segment"]["separators"],
                    "chunk_size": field.data["segment"]["chunk_size"],
                    "chunk_overlap": field.data["segment"]["chunk_overlap"],
                }
            }


class CreateDocumentsResp(Schema):
    """Response schema for creating documents"""
    documents = fields.List(fields.Dict, dump_default=[])
    batch = fields.String(dump_default="")

    @pre_dump
    def process_data(self, data: tuple[list[Document], str], **kwargs):
        return {
            "documents": [{
                "id": document.id,
                "name": document.name,
                "status": document.status,
                "created_at": int(document.created_at.timestamp())
            } for document in data[0]],
            "batch": data[1],
        }


class GetDocumentResp(Schema):
    """Response schema for basic document information"""
    id = fields.UUID(dump_default="")
    dataset_id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    segment_count = fields.Integer(dump_default=0)
    character_count = fields.Integer(dump_default=0)
    hit_count = fields.Integer(dump_default=0)
    position = fields.Integer(dump_default=0)
    enabled = fields.Bool(dump_default=False)
    disabled_at = fields.Integer(dump_default=0)
    status = fields.String(dump_default="")
    error = fields.String(dump_default="")
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Document, **kwargs):
        return {
            "id": data.id,
            "dataset_id": data.dataset_id,
            "name": data.name,
            "segment_count": data.segment_count,
            "character_count": data.character_count,
            "hit_count": data.hit_count,
            "position": data.position,
            "enabled": data.enabled,
            "disabled_at": datetime_to_timestamp(data.disabled_at),
            "status": data.status,
            "error": data.error,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }


class UpdateDocumentNameReq(FlaskForm):
    """Update document name/basic info request"""
    name = StringField("name", validators=[
        DataRequired("Document name cannot be empty"),
        Length(max=100, message="Document name cannot exceed 100 characters")
    ])


class GetDocumentsWithPageReq(PaginatorReq):
    """Get paginated documents request"""
    search_word = StringField("search_word", default="", validators=[
        Optional()
    ])


class GetDocumentsWithPageResp(Schema):
    """Get paginated documents response"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    character_count = fields.Integer(dump_default=0)
    hit_count = fields.Integer(dump_default=0)
    position = fields.Integer(dump_default=0)
    enabled = fields.Bool(dump_default=False)
    disabled_at = fields.Integer(dump_default=0)
    status = fields.String(dump_default="")
    error = fields.String(dump_default="")
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Document, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "character_count": data.character_count,
            "hit_count": data.hit_count,
            "position": data.position,
            "enabled": data.enabled,
            "disabled_at": datetime_to_timestamp(data.disabled_at),
            "status": data.status,
            "error": data.error,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }


class UpdateDocumentEnabledReq(FlaskForm):
    """Update document enabled status request"""
    enabled = BooleanField("enabled")

    def validate_enabled(self, field: BooleanField) -> None:
        """Validate 'enabled' flag"""
        if not isinstance(field.data, bool):
            raise ValidationError("enabled cannot be empty and must be a boolean")
