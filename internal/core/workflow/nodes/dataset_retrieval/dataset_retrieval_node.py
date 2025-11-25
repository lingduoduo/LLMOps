#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : dataset_retrieval_node.py
"""
import time
from typing import Optional, Any
from uuid import UUID

from flask import Flask
from langchain_core.pydantic_v1 import PrivateAttr
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from .dataset_retrieval_entity import DatasetRetrievalNodeData


class DatasetRetrievalNode(BaseNode):
    """Dataset / knowledge-base retrieval node."""
    node_data: DatasetRetrievalNodeData
    _retrieval_tool: BaseTool = PrivateAttr(None)

    def __init__(
            self,
            *args: Any,
            flask_app: Flask,
            account_id: UUID,
            **kwargs: Any,
    ):
        """
        Constructor for the dataset retrieval node.

        Initializes the internal retrieval tool using the dataset IDs
        and retrieval configuration from the node's metadata.
        """
        # 1. Initialize base fields from parent class
        super().__init__(*args, **kwargs)

        # 2. Resolve dependency-injected RetrievalService
        from app.http.module import injector
        from internal.service import RetrievalService

        retrieval_service = injector.get(RetrievalService)

        # 3. Build a LangChain-compatible retrieval tool
        self._retrieval_tool = retrieval_service.create_langchain_tool_from_search(
            flask_app=flask_app,
            dataset_ids=self.node_data.dataset_ids,
            account_id=account_id,
            **self.node_data.retrieval_config.dict(),
        )

    def invoke(
            self,
            state: WorkflowState,
            config: Optional[RunnableConfig] = None
    ) -> WorkflowState:
        """
        Execute the dataset retrieval node.

        Steps:
        1. Extract input variables from workflow state.
        2. Invoke the underlying retrieval tool.
        3. Store the combined retrieved documents as output.
        """
        # 1. Extract input values
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 2. Execute retrieval
        combine_documents = self._retrieval_tool.invoke(inputs_dict)

        # 3. Build output dictionary
        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = combine_documents
        else:
            outputs["combine_documents"] = combine_documents

        # 4. Build and return workflow node result
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }
