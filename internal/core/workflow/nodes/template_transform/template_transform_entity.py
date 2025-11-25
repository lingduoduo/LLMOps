#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : template_transform_entity.py
"""

from langchain_core.pydantic_v1 import Field

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity, VariableValueType


class TemplateTransformNodeData(BaseNodeData):
    """
    Data model for a template-transform node.

    Defines the Jinja2 template string, input variable bindings,
    and the default output variable used to store the rendered template result.
    """

    # Jinja2 template string to be rendered
    template: str = ""

    # Input variable bindings
    inputs: list[VariableEntity] = Field(default_factory=list)

    # Output variable definition (default: {"output": generated})
    outputs: list[VariableEntity] = Field(
        exclude=True,
        default_factory=lambda: [
            VariableEntity(
                name="output",
                value={"type": VariableValueType.GENERATED},
            )
        ],
    )
