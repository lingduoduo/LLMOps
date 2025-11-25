#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : code_entity.py
"""
from langchain_core.pydantic_v1 import Field

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity

# 默认的代码
DEFAULT_CODE = """
def main(params):
    return params
"""


class CodeNodeData(BaseNodeData):
    """Python code execution node data entity"""
    code: str = DEFAULT_CODE  # Need to execute the code
    inputs: list[VariableEntity] = Field(default_factory=list)  # Input variable list
    outputs: list[VariableEntity] = Field(default_factory=list)  # Output variable list
