#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : start_entity.py
"""
from langchain_core.pydantic_v1 import Field

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity


class StartNodeData(BaseNodeData):
    """Start Node Data Model"""
    inputs: list[VariableEntity] = Field(default_factory=list)
