#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : dataset_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.core.file_extractor import FileExtractor
from internal.schema.dataset_schema import (
    CreateDatasetReq,
    GetDatasetResp,
    UpdateDatasetReq,
    GetDatasetsWithPageReq,
    GetDatasetsWithPageResp,
    HitReq,
    GetDatasetQueriesResp,
)
from internal.service import (
    DatasetService,
    EmbeddingsService,
    JiebaService,
    VectorDatabaseService,
)
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_message, success_json
from pkg.sqlalchemy import SQLAlchemy


@inject
@dataclass
class DatasetHandler:
    """Handler for managing dataset (knowledge base) operations."""
    db: SQLAlchemy
    file_extractor: FileExtractor
    dataset_service: DatasetService
    embeddings_service: EmbeddingsService
    jieba_service: JiebaService
    vector_database_service: VectorDatabaseService

    @login_required
    def hit(self, dataset_id: UUID):
        """Execute a recall (retrieval) test using the given dataset ID and query parameters."""
        # 1. Extract and validate request data
        req = HitReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to perform retrieval strategy
        hit_result = self.dataset_service.hit(dataset_id, req, current_user)

        return success_json(hit_result)

    @login_required
    def get_dataset_queries(self, dataset_id: UUID):
        """Retrieve the latest 10 query records for the given dataset ID."""
        dataset_queries = self.dataset_service.get_dataset_queries(dataset_id, current_user)
        resp = GetDatasetQueriesResp(many=True)
        return success_json(resp.dump(dataset_queries))

    @login_required
    def create_dataset(self):
        """Create a new dataset (knowledge base)."""
        # 1. Extract request and validate
        req = CreateDatasetReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to create dataset
        self.dataset_service.create_dataset(req, current_user)

        # 3. Return success message
        return success_message("Dataset created successfully.")

    @login_required
    def get_dataset(self, dataset_id: UUID):
        """Retrieve dataset details by dataset ID."""
        dataset = self.dataset_service.get_dataset(dataset_id, current_user)
        resp = GetDatasetResp()
        return success_json(resp.dump(dataset))

    @login_required
    def update_dataset(self, dataset_id: UUID):
        """Update dataset information using the given dataset ID."""
        # 1. Extract request and validate
        req = UpdateDatasetReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to update dataset
        self.dataset_service.update_dataset(dataset_id, req, current_user)

        # 3. Return success message
        return success_message("Dataset updated successfully.")

    @login_required
    def delete_dataset(self, dataset_id: UUID):
        """Delete the dataset specified by dataset ID."""
        self.dataset_service.delete_dataset(dataset_id, current_user)
        return success_message("Dataset deleted successfully.")

    @login_required
    def get_datasets_with_page(self):
        """Retrieve a paginated and searchable list of datasets."""
        # 1. Extract query parameters and validate
        req = GetDatasetsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to fetch paginated dataset list
        datasets, paginator = self.dataset_service.get_datasets_with_page(req, current_user)

        # 3. Build response
        resp = GetDatasetsWithPageResp(many=True)
        return success_json(PageModel(list=resp.dump(datasets), paginator=paginator))
