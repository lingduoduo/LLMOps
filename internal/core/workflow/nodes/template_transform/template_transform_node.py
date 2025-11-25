#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : template_transform_node.py
"""

import time
from typing import Optional

from jinja2 import Template
from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from .template_transform_entity import TemplateTransformNodeData


class TemplateTransformNode(BaseNode):
    """Template transform node: merges multiple variables into a single text output."""
    node_data: TemplateTransformNodeData

    def invoke(
            self,
            state: WorkflowState,
            config: Optional[RunnableConfig] = None
    ) -> WorkflowState:
        """
        Execute the template transform node.

        Extracts input variables from the workflow state,
        renders them into the configured Jinja2 template,
        and returns the merged string as the output.
        """
        # 1. Extract input variable values
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 2. Render the Jinja2 template with the input variables
        template = Template(self.node_data.template)
        template_value = template.render(**inputs_dict)

        # 3. Build output payload
        outputs = {"output": template_value}

        # 4. Return workflow state update
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
