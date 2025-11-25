#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : tool_entity.py
"""

from typing import Any, Literal

from langchain_core.pydantic_v1 import Field

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import (
    VariableEntity,
    VariableValueType,
)


class ToolNodeData(BaseNodeData):
    """
    Data model for a tool node.

    Represents the metadata required to execute either a built-in tool
    or an API-based external tool within the workflow system.
    """

    # Type of tool: built-in or API-based
    tool_type: Literal["builtin_tool", "api_tool"] = Field(alias="type")

    # Provider identifier (e.g., built-in provider ID or API provider ID)
    provider_id: str

    # Tool identifier (e.g., tool name under a provider)
    tool_id: str

    # Parameters passed into the tool during initialization (for built-in tools)
    params: dict[str, Any] = Field(default_factory=dict)

    # Input variable bindings for this tool node
    inputs: list[VariableEntity] = Field(default_factory=list)

    # Output variable definitions
    # By default, one output named "text" is generated unless explicitly overridden.
    outputs: list[VariableEntity] = Field(
        exclude=True,
        default_factory=lambda: [
            VariableEntity(
                name="text",
                value={"type": VariableValueType.GENERATED},
            )
        ],
    )
