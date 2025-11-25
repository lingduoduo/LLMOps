#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : edge_entity.py
"""
from uuid import UUID

from langchain_core.pydantic_v1 import BaseModel

from internal.core.workflow.entities.node_entity import NodeType


class BaseEdgeData(BaseModel):
    """Base edge metadata."""
    id: UUID  # Unique edge identifier
    source: UUID  # Edge source node id
    source_type: NodeType  # Edge source type
    target: UUID  # Edge target node id
    target_type: NodeType  # Edge target type
