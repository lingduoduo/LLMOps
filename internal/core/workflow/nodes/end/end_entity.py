#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : end_entity.py
"""
from langchain_core.pydantic_v1 import Field

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity


class EndNodeData(BaseNodeData):
    """End Node Data Model"""
    outputs: list[VariableEntity] = Field(default_factory=list)
