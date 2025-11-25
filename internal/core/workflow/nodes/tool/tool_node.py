#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : tool_node.py
"""

import json
import time
from typing import Optional, Any

from langchain_core.pydantic_v1 import PrivateAttr
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from internal.core.tools.api_tools.entities import ToolEntity
from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from internal.exception import FailException, NotFoundException
from internal.model import ApiTool
from .tool_entity import ToolNodeData


class ToolNode(BaseNode):
    """Tool node for executing built-in or API-based extensions."""

    node_data: ToolNodeData
    _tool: BaseTool = PrivateAttr(None)

    def __init__(self, *args: Any, **kwargs: Any):
        """Constructor. Initializes the tool instance (built-in or API-based)."""
        # 1. Call the parent constructor to initialize base data
        super().__init__(*args, **kwargs)

        # 2. Get DI injector
        from app.http.module import injector

        # 3. Determine whether this node uses a built-in tool or an API tool
        if self.node_data.tool_type == "builtin_tool":
            from internal.core.tools.builtin_tools.providers import BuiltinProviderManager

            builtin_provider_manager = injector.get(BuiltinProviderManager)

            # 4. Retrieve the built-in tool instance
            _tool = builtin_provider_manager.get_tool(
                self.node_data.provider_id,
                self.node_data.tool_id,
            )
            if not _tool:
                raise NotFoundException("Built-in tool not found. Please verify and retry.")

            # Initialize the built-in tool with parameters
            self._tool = _tool(**self.node_data.params)

        else:
            # 5. API-based tool: query database to load the configuration
            from pkg.sqlalchemy import SQLAlchemy
            db = injector.get(SQLAlchemy)

            # 6. Look up API tool by provider + tool name
            api_tool = (
                db.session.query(ApiTool)
                .filter(
                    ApiTool.provider_id == self.node_data.provider_id,
                    ApiTool.name == self.node_data.tool_id,
                )
                .one_or_none()
            )
            if not api_tool:
                raise NotFoundException("API tool not found. Please verify and retry.")

            # 7. Load API provider manager
            from internal.core.tools.api_tools.providers import ApiProviderManager

            api_provider_manager = injector.get(ApiProviderManager)

            # 8. Create API tool instance
            self._tool = api_provider_manager.get_tool(
                ToolEntity(
                    id=str(api_tool.id),
                    name=api_tool.name,
                    url=api_tool.url,
                    method=api_tool.method,
                    description=api_tool.description,
                    headers=api_tool.provider.headers,
                    parameters=api_tool.parameters,
                )
            )

    def invoke(
            self,
            state: WorkflowState,
            config: Optional[RunnableConfig] = None,
    ) -> WorkflowState:
        """
        Executes the tool with the inputs extracted from the workflow state.
        Supports both built-in tools and external API tool integrations.
        """
        # 1. Extract node input variables from state
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 2. Run the tool
        try:
            result = self._tool.invoke(inputs_dict)
        except Exception:
            raise FailException("Tool execution failed. Please try again later.")

        # 3. Normalize output to string
        if not isinstance(result, str):
            result = json.dumps(result)

        # 4. Map output to configured output variable
        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = result
        else:
            outputs["text"] = result

        # 5. Build workflow state update
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
