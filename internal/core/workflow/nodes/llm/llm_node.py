#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : llm_node.py
"""

import time
from typing import Optional

from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from .llm_entity import LLMNodeData


class LLMNode(BaseNode):
    """Node for invoking a Large Language Model."""
    node_data: LLMNodeData

    def invoke(
            self,
            state: WorkflowState,
            config: Optional[RunnableConfig] = None
    ) -> WorkflowState:
        """
        Execute the LLM node.

        1. Extract input variables.
        2. Render the prompt using Jinja2.
        3. Create an LLM instance (currently ChatOpenAI; extendable).
        4. Stream LLM output to avoid long-time blocking.
        5. Return output as workflow node result.
        """
        # 1. Extract input variables
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 2. Render prompt with Jinja2
        template = Template(self.node_data.prompt)
        prompt_value = template.render(**inputs_dict)

        # 3. Create LLM instance (supports future multi-model config)
        llm = ChatOpenAI(
            model=self.node_data.language_model_config.get("model", "gpt-4o-mini"),
            **self.node_data.language_model_config.get("parameters", {}),
        )

        # 4. Stream output to avoid timeout
        content = ""
        for chunk in llm.stream(prompt_value):
            content += chunk.content

        # 5. Build output dictionary
        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = content
        else:
            outputs["output"] = content

        # 6. Build workflow state update
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
