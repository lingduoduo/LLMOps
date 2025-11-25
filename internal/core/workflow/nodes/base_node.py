#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : base_node.py
"""
from abc import ABC

from langchain_core.runnables import RunnableSerializable

from internal.core.workflow.entities.node_entity import BaseNodeData


class BaseNode(RunnableSerializable, ABC):
    """BaseNode for workflow nodes"""
    node_data: BaseNodeData
