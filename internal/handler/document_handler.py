#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : document_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import current_user, login_required
from injector import inject

from internal.schema.document_schema import (
    CreateDocumentsReq,
    CreateDocumentsResp,
    GetDocumentResp,
    UpdateDocumentNameReq,
    GetDocumentsWithPageReq,
    GetDocumentsWithPageResp,
    UpdateDocumentEnabledReq,
)
from internal.service import DocumentService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_json, success_message


@inject
@dataclass
class DocumentHandler:
    """Document handler"""
    document_service: DocumentService

    @login_required
    def create_documents(self, dataset_id: UUID):
        """Create/upload a list of documents for the specified dataset."""
        # 1. Extract request and validate
        req = CreateDocumentsReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to create documents and return document list + batch ID
        documents, batch = self.document_service.create_documents(dataset_id, **req.data, account=current_user)

        # 3. Build response structure and return
        resp = CreateDocumentsResp()

        return success_json(resp.dump((documents, batch)))

    @login_required
    def get_document(self, dataset_id: UUID, document_id: UUID):
        """Get document details by dataset ID and document ID."""
        document = self.document_service.get_document(dataset_id, document_id, current_user)

        resp = GetDocumentResp()

        return success_json(resp.dump(document))

    @login_required
    def update_document_name(self, dataset_id: UUID, document_id: UUID):
        """Update the name of a document by dataset ID and document ID."""
        # 1. Extract request and validate data
        req = UpdateDocumentNameReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to update the document name
        self.document_service.update_document(dataset_id, document_id, account=current_user, name=req.name.data)

        return success_message("Document name updated successfully.")

    @login_required
    def update_document_enabled(self, dataset_id: UUID, document_id: UUID):
        """Update the enabled/disabled status of a document by dataset ID and document ID."""
        # 1. Extract request and validate
        req = UpdateDocumentEnabledReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to update the document status
        self.document_service.update_document_enabled(dataset_id, document_id, req.enabled.data, current_user)

        return success_message("Document enabled status updated successfully.")

    @login_required
    def delete_document(self, dataset_id: UUID, document_id: UUID):
        """Delete a document by dataset ID and document ID."""
        self.document_service.delete_document(dataset_id, document_id, current_user)

        return success_message("Document deleted successfully.")

    @login_required
    def get_documents_with_page(self, dataset_id: UUID):
        """Get a paginated list of documents for the specified dataset."""
        # 1. Extract query parameters and validate
        req = GetDocumentsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to get paginated document list and paginator
        documents, paginator = self.document_service.get_documents_with_page(dataset_id, req, current_user)

        # 3. Build response structure and map results
        resp = GetDocumentsWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(documents), paginator=paginator))

    @login_required
    def get_documents_status(self, dataset_id: UUID, batch: str):
        """Get the processing status of documents by dataset ID and batch identifier."""
        documents_status = self.document_service.get_documents_status(dataset_id, batch, current_user)

        return success_json(documents_status)
