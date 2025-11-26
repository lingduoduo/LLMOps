#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : start_node.py
"""

import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.variable_entity import VARIABLE_TYPE_DEFAULT_VALUE_MAP
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.exception import FailException
from .start_entity import StartNodeData


class StartNode(BaseNode):
    """Start node — entry point of the workflow."""
    node_data: StartNodeData

    def invoke(
            self,
            state: WorkflowState,
            config: Optional[RunnableConfig] = None
    ) -> WorkflowState:
        """
        Execute the start node.

        Extracts input values from the workflow state, validates them
        according to required/optional rules, assigns default values when needed,
        and produces the initial output payload.
        """
        # 1. Extract input field definitions from node metadata
        start_at = time.perf_counter()
        inputs = self.node_data.inputs

        # 2. Validate and collect input values
        outputs = {}
        for input in inputs:
            input_value = state["inputs"].get(input.name, None)

            # 3. Check required fields
            if input_value is None:
                if input.required:
                    # Required but missing → fail immediately
                    raise FailException(
                        f"Workflow input error: '{input.name}' is a required parameter."
                    )
                else:
                    # Optional → apply default value based on variable type
                    input_value = VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(input.type)

            # 4. Store parsed/validated input
            outputs[input.name] = input_value

        # 5. Build workflow state update (node result)
        return {"node_results": [
            NodeResult(
                node_data=self.node_data,
                status=NodeStatus.SUCCEEDED,
                inputs=state["inputs"],
                outputs=outputs,
                latency=(time.perf_counter() - start_at),
            )
        ]
        }
