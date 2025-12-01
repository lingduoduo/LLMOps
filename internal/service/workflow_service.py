#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : workflow_service.py
"""
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Generator
from uuid import UUID

from flask import request
from injector import inject
from sqlalchemy import desc

from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.core.workflow import Workflow as WorkflowTool
from internal.core.workflow.entities.edge_entity import BaseEdgeData
from internal.core.workflow.entities.node_entity import NodeType, BaseNodeData
from internal.core.workflow.entities.workflow_entity import WorkflowConfig
from internal.core.workflow.nodes import (
    CodeNodeData,
    DatasetRetrievalNodeData,
    EndNodeData,
    HttpRequestNodeData,
    LLMNodeData,
    StartNodeData,
    TemplateTransformNodeData,
    ToolNodeData,
)
from internal.entity.workflow_entity import WorkflowStatus, DEFAULT_WORKFLOW_CONFIG, WorkflowResultStatus
from internal.exception import ValidateErrorException, NotFoundException, ForbiddenException, FailException
from internal.lib.helper import convert_model_to_dict
from internal.model import Account, Workflow, Dataset, ApiTool, WorkflowResult
from internal.schema.workflow_schema import CreateWorkflowReq, GetWorkflowsWithPageReq
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class WorkflowService(BaseService):
    """Workflow service"""
    db: SQLAlchemy
    builtin_provider_manager: BuiltinProviderManager

    def create_workflow(self, req: CreateWorkflowReq, account: Account) -> Workflow:
        """Create a workflow based on the request data"""
        # 1. Check whether a workflow with the same tool_call_name already exists under this account
        check_workflow = self.db.session.query(Workflow).filter(
            Workflow.tool_call_name == req.tool_call_name.data.strip(),
            Workflow.account_id == account.id,
        ).one_or_none()
        if check_workflow:
            raise ValidateErrorException(
                f"A workflow named [{req.tool_call_name.data}] already exists for this account; duplicate names are not allowed"
            )

        # 2. Create the workflow in the database
        return self.create(
            Workflow,
            **{
                **req.data,
                **DEFAULT_WORKFLOW_CONFIG,
                "account_id": account.id,
                "is_debug_passed": False,
                "status": WorkflowStatus.DRAFT,
                "tool_call_name": req.tool_call_name.data.strip(),
            },
        )

    def get_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """Get workflow basic information by workflow_id"""
        # 1. Query workflow basic information
        workflow = self.get(Workflow, workflow_id)

        # 2. Check whether the workflow exists
        if not workflow:
            raise NotFoundException("The workflow does not exist, please verify and try again")

        # 3. Check whether the current account has access to this workflow
        if workflow.account_id != account.id:
            raise ForbiddenException(
                "The current account is not allowed to access this workflow, please verify and try again")

        return workflow

    def delete_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """Delete a workflow by workflow_id and account"""
        # 1. Get workflow basic information and check permission
        workflow = self.get_workflow(workflow_id, account)

        # 2. Delete the workflow
        self.delete(workflow)

        return workflow

    def update_workflow(self, workflow_id: UUID, account: Account, **kwargs) -> Workflow:
        """Update workflow basic information by workflow_id and request data"""
        # 1. Get workflow basic information and check permission
        workflow = self.get_workflow(workflow_id, account)

        # 2. Check whether another workflow with the same tool_call_name exists under this account
        check_workflow = self.db.session.query(Workflow).filter(
            Workflow.tool_call_name == kwargs.get("tool_call_name", "").strip(),
            Workflow.account_id == account.id,
            Workflow.id != workflow.id,
        ).one_or_none()
        if check_workflow:
            raise ValidateErrorException(
                f"A workflow named [{kwargs.get('tool_call_name', '')}] already exists for this account; duplicate names are not allowed"
            )

        # 3. Update workflow basic information
        self.update(workflow, **kwargs)

        return workflow

    def get_workflows_with_page(
            self, req: GetWorkflowsWithPageReq, account: Account
    ) -> tuple[list[Workflow], Paginator]:
        """Get a paginated list of workflows based on the request data"""
        # 1. Build paginator
        paginator = Paginator(db=self.db, req=req)

        # 2. Build filters
        filters = [Workflow.account_id == account.id]
        if req.search_word.data:
            filters.append(Workflow.name.ilike(f"%{req.search_word.data}%"))
        if req.status.data:
            filters.append(Workflow.status == req.status.data)

        # 3. Query workflows with pagination
        workflows = paginator.paginate(
            self.db.session.query(Workflow).filter(*filters).order_by(desc("created_at"))
        )

        return workflows, paginator

    def update_draft_graph(self, workflow_id: UUID, draft_graph: dict[str, Any], account: Account) -> Workflow:
        """Update the draft graph of a workflow by workflow_id + draft_graph + account"""
        # 1. Get workflow and check permission
        workflow = self.get_workflow(workflow_id, account)

        # 2. Validate the draft graph config; edges may not be fully established yet, so we need to validate referenced data
        validate_draft_graph = self._validate_graph(draft_graph, account)

        # 3. Update the draft_graph config and reset is_debug_passed to False each time (can be optimized later)
        self.update(
            workflow,
            **{
                "draft_graph": validate_draft_graph,
                "is_debug_passed": False,
            },
        )

        return workflow

    def get_draft_graph(self, workflow_id: UUID, account: Account) -> dict[str, Any]:
        """Get draft graph configuration of a workflow by workflow_id + account"""
        # 1. Get workflow and check permission
        workflow = self.get_workflow(workflow_id, account)

        # 2. Extract draft_graph and validate it (without writing back to DB)
        draft_graph = workflow.draft_graph
        validate_draft_graph = self._validate_graph(draft_graph, account)

        # 3. Iterate over nodes and attach metadata for tool/dataset nodes
        for node in validate_draft_graph["nodes"]:
            if node.get("node_type") == NodeType.TOOL:
                # 4. Handle different tool types
                if node.get("tool_type") == "builtin_tool":
                    # 5. For builtin tool nodes, attach tool name, icon, params, etc.
                    provider = self.builtin_provider_manager.get_provider(node.get("provider_id"))
                    if not provider:
                        continue

                    # 6. Get tool entity from provider and check existence
                    tool_entity = provider.get_tool_entity(node.get("tool_id"))
                    if not tool_entity:
                        continue

                    # 7. Validate params; if they differ from the tool definition, reset to defaults
                    param_keys = {param.name for param in tool_entity.params}
                    params = node.get("params")
                    if set(params.keys()) - param_keys:
                        params = {
                            param.name: param.default
                            for param in tool_entity.params
                            if param.default is not None
                        }

                    # 8. Attach metadata for display
                    provider_entity = provider.provider_entity
                    node["meta"] = {
                        "type": "builtin_tool",
                        "provider": {
                            "id": provider_entity.name,
                            "name": provider_entity.name,
                            "label": provider_entity.label,
                            "icon": f"{request.scheme}://{request.host}/builtin-tools/{provider_entity.name}/icon",
                            "description": provider_entity.description,
                        },
                        "tool": {
                            "id": tool_entity.name,
                            "name": tool_entity.name,
                            "label": tool_entity.label,
                            "description": tool_entity.description,
                            "params": params,
                        },
                    }
                else:
                    # 9. For API tools, query DB to get tool record and check existence
                    tool_record = self.db.session.query(ApiTool).filter(
                        ApiTool.provider_id == node.get("provider_id"),
                        ApiTool.name == node.get("tool_id"),
                        ApiTool.account_id == account.id,
                    ).one_or_none()
                    if not tool_record:
                        continue

                    # 10. Build API tool metadata for display
                    provider = tool_record.provider
                    node["meta"] = {
                        "type": "api_tool",
                        "provider": {
                            "id": str(provider.id),
                            "name": provider.name,
                            "label": provider.name,
                            "icon": provider.icon,
                            "description": provider.description,
                        },
                        "tool": {
                            "id": str(tool_record.id),
                            "name": tool_record.name,
                            "label": tool_record.name,
                            "description": tool_record.description,
                            "params": {},
                        },
                    }
            elif node.get("node_type") == NodeType.DATASET_RETRIEVAL:
                # 5. For dataset retrieval nodes, attach dataset names, icons, etc.
                datasets = self.db.session.query(Dataset).filter(
                    Dataset.id.in_(node.get("dataset_ids", [])),
                    Dataset.account_id == account.id,
                ).all()
                node["meta"] = {
                    "datasets": [
                        {
                            "id": dataset.id,
                            "name": dataset.name,
                            "icon": dataset.icon,
                            "description": dataset.description,
                        }
                        for dataset in datasets
                    ]
                }

        return validate_draft_graph

    def debug_workflow(self, workflow_id: UUID, inputs: dict[str, Any], account: Account) -> Generator:
        """Debug the specified workflow API; this endpoint streams events"""
        # 1. Get workflow and check permission
        workflow = self.get_workflow(workflow_id, account)

        # 2. Create a workflow tool instance
        workflow_tool = WorkflowTool(
            workflow_config=WorkflowConfig(
                account_id=account.id,
                name=workflow.tool_call_name,
                description=workflow.description,
                nodes=workflow.draft_graph.get("nodes", []),
                edges=workflow.draft_graph.get("edges", []),
            )
        )

        def handle_stream() -> Generator:
            # 3. Store all node execution results
            node_results = []

            # 4. Create a WorkflowResult record in DB
            workflow_result = self.create(
                WorkflowResult,
                **{
                    "app_id": None,
                    "account_id": account.id,
                    "workflow_id": workflow.id,
                    "graph": workflow.draft_graph,
                    "state": [],
                    "latency": 0,
                    "status": WorkflowResultStatus.RUNNING,
                },
            )

            # 4. Call workflow_tool.stream to get streaming results
            start_at = time.perf_counter()
            try:
                for chunk in workflow_tool.stream(inputs):
                    # 5. chunk format: {"node_name": WorkflowState}, so we take the first key
                    first_key = next(iter(chunk))

                    # 6. Extract node execution result
                    node_result = chunk[first_key]["node_results"][0]
                    node_result_dict = convert_model_to_dict(node_result)
                    node_results.append(node_result_dict)

                    # 7. Build response data and stream as SSE
                    data = {
                        "id": str(uuid.uuid4()),
                        **node_result_dict,
                    }
                    yield f"event: workflow\ndata: {json.dumps(data)}\n\n"

                # 7. After streaming finishes, persist results into DB
                self.update(
                    workflow_result,
                    **{
                        "status": WorkflowResultStatus.SUCCEEDED,
                        "state": node_results,
                        "latency": (time.perf_counter() - start_at),
                    },
                )
                self.update(
                    workflow,
                    **{
                        "is_debug_passed": True,
                    },
                )
            except Exception:
                self.update(
                    workflow_result,
                    **{
                        "status": WorkflowResultStatus.FAILED,
                        "state": node_results,
                        "latency": (time.perf_counter() - start_at),
                    },
                )

        return handle_stream()

    def publish_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """Publish a workflow by workflow_id"""
        # 1. Get workflow and check permission
        workflow = self.get_workflow(workflow_id, account)

        # 2. Check whether the workflow has passed debugging
        if workflow.is_debug_passed is False:
            raise FailException("This workflow has not passed debugging; please debug successfully before publishing")
        if workflow.status == WorkflowStatus.PUBLISHED:
            raise FailException("This workflow is already published; no need to publish again")

        # 3. Validate configuration using WorkflowConfig; if validation fails, do not publish
        try:
            WorkflowConfig(
                account_id=account.id,
                name=workflow.tool_call_name,
                description=workflow.description,
                nodes=workflow.draft_graph.get("nodes", []),
                edges=workflow.draft_graph.get("edges", []),
            )
        except Exception:
            self.update(
                workflow,
                **{
                    "is_debug_passed": False,
                },
            )
            raise ValidateErrorException("Workflow configuration validation failed; please verify and try again")

        # 4. Update workflow publish status
        self.update(
            workflow,
            **{
                "graph": workflow.draft_graph,
                "status": WorkflowStatus.PUBLISHED,
                "is_debug_passed": False,
            },
        )

        return workflow

    def cancel_publish_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """Cancel publication of the specified workflow"""
        # 1. Get workflow and check permission
        workflow = self.get_workflow(workflow_id, account)

        # 2. Ensure workflow is currently published
        if workflow.status != WorkflowStatus.PUBLISHED:
            raise FailException("This workflow is not published and cannot be unpublished")

        # 3. Reset publish status and clear runtime graph
        self.update(
            workflow,
            **{
                "graph": {},
                "status": WorkflowStatus.DRAFT,
                "is_debug_passed": False,
            },
        )

        return workflow

    def _validate_graph(self, graph: dict[str, Any], account: Account) -> dict[str, Any]:
        """
        Validate the given graph information, including nodes and edges.

        This uses relatively loose validation since it's for drafts,
        and we don't require strict consistency of nodes/edges relationships.
        """
        # 1. Extract nodes and edges
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        # 2. Build a mapping from node_type to node data class
        node_data_classes = {
            NodeType.START: StartNodeData,
            NodeType.END: EndNodeData,
            NodeType.LLM: LLMNodeData,
            NodeType.TEMPLATE_TRANSFORM: TemplateTransformNodeData,
            NodeType.DATASET_RETRIEVAL: DatasetRetrievalNodeData,
            NodeType.CODE: CodeNodeData,
            NodeType.TOOL: ToolNodeData,
            NodeType.HTTP_REQUEST: HttpRequestNodeData,
        }

        # 3. Validate each node in nodes
        node_data_dict: dict[UUID, BaseNodeData] = {}
        start_nodes = 0
        end_nodes = 0
        for node in nodes:
            try:
                # 4. Node must be a dict
                if not isinstance(node, dict):
                    raise ValidateErrorException("Workflow node data type is incorrect; please verify and try again")

                # 5. Extract node_type and check existence
                node_type = node.get("node_type", "")
                node_data_cls = node_data_classes.get(node_type, None)
                if node_data_cls is None:
                    raise ValidateErrorException("Workflow node type is incorrect; please verify and try again")

                # 6. Instantiate node data class
                node_data = node_data_cls(**node)

                # 7. Check node id uniqueness
                if node_data.id in node_data_dict:
                    raise ValidateErrorException("Workflow node id must be unique; please verify and try again")

                # 8. Check node title uniqueness
                if any(item.title.strip() == node_data.title.strip() for item in node_data_dict.values()):
                    raise ValidateErrorException("Workflow node title must be unique; please verify and try again")

                # 9. Special checks for start / end / dataset / tool nodes
                if node_data.node_type == NodeType.START:
                    if start_nodes >= 1:
                        raise ValidateErrorException("Only one start node is allowed in a workflow")
                    start_nodes += 1
                elif node_data.node_type == NodeType.END:
                    if end_nodes >= 1:
                        raise ValidateErrorException("Only one end node is allowed in a workflow")
                    end_nodes += 1
                elif node_data.node_type == NodeType.DATASET_RETRIEVAL:
                    # 10. Filter dataset_ids to keep only those belonging to the current account (limit first 5)
                    datasets = self.db.session.query(Dataset).filter(
                        Dataset.id.in_(node_data.dataset_ids[:5]),
                        Dataset.account_id == account.id,
                    ).all()
                    node_data.dataset_ids = [dataset.id for dataset in datasets]
                elif node_data.node_type == NodeType.TOOL:
                    # 11. Handle tool nodes differently based on tool_type
                    if node_data.tool_type == "builtin_tool":
                        tool = self.builtin_provider_manager.get_tool(node_data.provider_id, node_data.tool_id)
                        if not tool:
                            raise ValidateErrorException("The builtin tool bound to this tool node does not exist")
                    else:
                        # 12. API tool: ensure the tool belongs to the current account
                        tool_record = self.db.session.query(ApiTool).filter(
                            ApiTool.provider_id == node_data.provider_id,
                            ApiTool.name == node_data.tool_id,
                            ApiTool.account_id == account.id,
                        ).one_or_none()
                        if not tool_record:
                            raise ValidateErrorException("The API tool bound to this tool node does not exist")

                # 13. Add node_data to node_data_dict
                node_data_dict[node_data.id] = node_data
            except Exception:
                # Skip invalid nodes
                continue

        # 14. Validate each edge in edges
        edge_data_dict: dict[UUID, BaseEdgeData] = {}
        for edge in edges:
            try:
                # 15. Edge must be a dict
                if not isinstance(edge, dict):
                    raise ValidateErrorException("Workflow edge data type is incorrect; please verify and try again")
                edge_data = BaseEdgeData(**edge)

                # 16. Check edge id uniqueness
                if edge_data.id in edge_data_dict:
                    raise ValidateErrorException("Workflow edge id must be unique; please verify and try again")

                # 17. Validate that source/target and types match nodes
                if (
                        edge_data.source not in node_data_dict
                        or edge_data.source_type != node_data_dict[edge_data.source].node_type
                        or edge_data.target not in node_data_dict
                        or edge_data.target_type != node_data_dict[edge_data.target].node_type
                ):
                    raise ValidateErrorException(
                        "The source/target node of the workflow edge does not exist or has an incorrect type; please verify and try again"
                    )

                # 18. Ensure (source, target) pair is unique
                if any(
                        (item.source == edge_data.source and item.target == edge_data.target)
                        for item in edge_data_dict.values()
                ):
                    raise ValidateErrorException("Duplicate workflow edges are not allowed")

                # 19. If validation passes, add edge_data to edge_data_dict
                edge_data_dict[edge_data.id] = edge_data
            except Exception:
                # Skip invalid edges
                continue

        return {
            "nodes": [convert_model_to_dict(node_data) for node_data in node_data_dict.values()],
            "edges": [convert_model_to_dict(edge_data) for edge_data in edge_data_dict.values()],
        }
