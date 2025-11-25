#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : end_node.py
"""
import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from .end_entity import EndNodeData


class EndNode(BaseNode):
    """End node — final step of the workflow."""
    node_data: EndNodeData

    def invoke(
            self,
            state: WorkflowState,
            config: Optional[RunnableConfig] = None
    ) -> WorkflowState:
        """
        Execute the end node.

        Extracts the final output variables from the workflow state and
        returns them as the workflow's overall output.
        """
        # 1. Extract output variables
        start_at = time.perf_counter()
        outputs_dict = extract_variables_from_state(self.node_data.outputs, state)

        # 2. Build and return workflow result
        return {
            "outputs": outputs_dict,
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs={},
                    outputs=outputs_dict,
                    latency=(time.perf_counter() - start_at),
                )
            ],
        }
