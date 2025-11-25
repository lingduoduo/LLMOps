#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : llm_entity.py
"""

from typing import Any

from langchain_core.pydantic_v1 import Field

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import (
    VariableEntity,
    VariableValueType,
)
from internal.entity.app_entity import DEFAULT_APP_CONFIG


class LLMNodeData(BaseNodeData):
    """
    Data model for an LLM node.

    Defines the prompt template, model configuration,
    and input/output variable bindings for a Large Language Model node.
    """

    # Prompt template (Jinja2 string)
    prompt: str

    # Model configuration (e.g., {"model": "...", "parameters": {...}})
    language_model_config: dict[str, Any] = Field(
        alias="model_config",
        default_factory=lambda: DEFAULT_APP_CONFIG["model_config"],
    )

    # Input variable definitions
    inputs: list[VariableEntity] = Field(default_factory=list)

    # Output variable definition (default: "output")
    outputs: list[VariableEntity] = Field(
        exclude=True,
        default_factory=lambda: [
            VariableEntity(
                name="output",
                value={"type": VariableValueType.GENERATED},
            )
        ],
    )
