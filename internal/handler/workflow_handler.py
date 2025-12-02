#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : workflow_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import current_user, login_required
from injector import inject

from internal.schema.workflow_schema import (
    CreateWorkflowReq,
    UpdateWorkflowReq,
    GetWorkflowResp,
    GetWorkflowsWithPageReq,
    GetWorkflowsWithPageResp,
)
from internal.service import WorkflowService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_json, success_message, compact_generate_response


@inject
@dataclass
class WorkflowHandler:
    """Workflow handler"""
    workflow_service: WorkflowService

    @login_required
    def create_workflow(self):
        """Create a new workflow"""
        # 1. Extract request and validate
        req = CreateWorkflowReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to create workflow
        workflow = self.workflow_service.create_workflow(req, current_user)

        return success_json({"id": workflow.id})

    @login_required
    def delete_workflow(self, workflow_id: UUID):
        """Delete a workflow by its ID"""
        self.workflow_service.delete_workflow(workflow_id, current_user)
        return success_message("Workflow deleted successfully")

    @login_required
    def update_workflow(self, workflow_id: UUID):
        """Update workflow basic information by workflow ID"""
        # 1. Extract request and validate
        req = UpdateWorkflowReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Call service to update workflow data
        self.workflow_service.update_workflow(workflow_id, current_user, **req.data)

        return success_message("Workflow basic information updated successfully")

    @login_required
    def get_workflow(self, workflow_id: UUID):
        """Get workflow details by workflow ID"""
        workflow = self.workflow_service.get_workflow(workflow_id, current_user)
        resp = GetWorkflowResp()
        return success_json(resp.dump(workflow))

    @login_required
    def get_workflows_with_page(self):
        """Get a paginated list of workflows for the current logged-in account"""
        # 1. Extract query params and validate
        req = GetWorkflowsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. Get paginated workflow list
        workflows, paginator = self.workflow_service.get_workflows_with_page(req, current_user)

        # 3. Build response and return
        resp = GetWorkflowsWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(workflows), paginator=paginator))

    @login_required
    def update_draft_graph(self, workflow_id: UUID):
        """Update the draft graph configuration of a workflow by ID"""
        # 1. Extract draft graph JSON from request body
        draft_graph_dict = request.get_json(force=True, silent=True) or {
            "nodes": [],
            "edges": [],
        }

        # 2. Call service to update workflow draft graph configuration
        self.workflow_service.update_draft_graph(workflow_id, draft_graph_dict, current_user)

        return success_message("Workflow draft configuration updated successfully")

    @login_required
    def get_draft_graph(self, workflow_id: UUID):
        """Get draft graph configuration of a workflow by ID"""
        draft_graph = self.workflow_service.get_draft_graph(workflow_id, current_user)
        return success_json(draft_graph)

    @login_required
    def debug_workflow(self, workflow_id: UUID):
        """Debug a workflow by ID with the given input variables"""
        # 1. Extract user input variables
        inputs = request.get_json(force=True, silent=True) or {}

        # 2. Call service to debug the specified workflow
        response = self.workflow_service.debug_workflow(workflow_id, inputs, current_user)

        return compact_generate_response(response)

    @login_required
    def publish_workflow(self, workflow_id: UUID):
        """Publish a workflow by ID"""
        self.workflow_service.publish_workflow(workflow_id, current_user)
        return success_message("Workflow published successfully")

    @login_required
    def cancel_publish_workflow(self, workflow_id: UUID):
        """Cancel publication of a workflow by ID"""
        self.workflow_service.cancel_publish_workflow(workflow_id, current_user)
        return success_message("Workflow publication cancelled successfully")
