#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : segment_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.schema.segment_schema import (
    GetSegmentsWithPageReq,
    GetSegmentsWithPageResp,
    GetSegmentResp,
    UpdateSegmentEnabledReq,
    CreateSegmentReq,
    UpdateSegmentReq,
)
from internal.service import SegmentService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_json, success_message


@inject
@dataclass
class SegmentHandler:
    """Segment Handler"""
    segment_service: SegmentService

    @login_required
    def create_segment(self, dataset_id: UUID, document_id: UUID):
        """Create a document segment for a specific dataset and document."""
        # 1. Extract request and validate
        req = CreateSegmentReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to create a new segment record
        self.segment_service.create_segment(dataset_id, document_id, req, current_user)

        return success_message("Document segment created successfully.")

    @login_required
    def get_segments_with_page(self, dataset_id: UUID, document_id: UUID):
        """Retrieve a paginated list of segments for a given dataset document."""
        # 1. Extract and validate request parameters
        req = GetSegmentsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to get segment list and pagination data
        segments, paginator = self.segment_service.get_segments_with_page(dataset_id, document_id, req, current_user)

        # 3. Build response and return
        resp = GetSegmentsWithPageResp(many=True)
        return success_json(PageModel(list=resp.dump(segments), paginator=paginator))

    @login_required
    def get_segment(self, dataset_id: UUID, document_id: UUID, segment_id: UUID):
        """Retrieve details of a specific document segment."""
        segment = self.segment_service.get_segment(dataset_id, document_id, segment_id, current_user)
        resp = GetSegmentResp()
        return success_json(resp.dump(segment))

    @login_required
    def update_segment_enabled(self, dataset_id: UUID, document_id: UUID, segment_id: UUID):
        """Update the enabled/disabled status of a specific document segment."""
        # 1. Extract request and validate
        req = UpdateSegmentEnabledReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to update segment enabled status
        self.segment_service.update_segment_enabled(dataset_id, document_id, segment_id, req.enabled.data, current_user)

        return success_message("Segment status updated successfully.")

    @login_required
    def delete_segment(self, dataset_id: UUID, document_id: UUID, segment_id: UUID):
        """Delete a specific document segment."""
        self.segment_service.delete_segment(dataset_id, document_id, segment_id, current_user)
        return success_message("Document segment deleted successfully.")

    @login_required
    def update_segment(self, dataset_id: UUID, document_id: UUID, segment_id: UUID):
        """Update information for a specific document segment."""
        # 1. Extract request and validate
        req = UpdateSegmentReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to update segment information
        self.segment_service.update_segment(dataset_id, document_id, segment_id, req, current_user)

        return success_message("Document segment updated successfully.")
