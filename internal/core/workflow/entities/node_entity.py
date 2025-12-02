#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : node_entity.py
"""
from enum import Enum
from typing import Any
from uuid import UUID

from langchain_core.pydantic_v1 import BaseModel, Field


class NodeType(str, Enum):
    """Available node types."""
    START = "start"
    LLM = "llm"
    TOOL = "tool"
    CODE = "code"
    DATASET_RETRIEVAL = "dataset_retrieval"
    HTTP_REQUEST = "http_request"
    TEMPLATE_TRANSFORM = "template_transform"
    END = "end"


class BaseNodeData(BaseModel):
    """Basic node metadata."""

    class Position(BaseModel):
        """Position of the node in the UI canvas."""
        x: float = 0.0
        y: float = 0.0

    class Config:
        allow_population_by_field_name = True

    id: UUID  # Unique node ID
    node_type: NodeType  # Node type
    title: str = ""  # Node title (must be unique)
    description: str = ""  # Node description
    position: Position = Field(  # Node coordinates
        default_factory=lambda: BaseNodeData.Position(x=0, y=0)
    )


class NodeStatus(str, Enum):
    """Node execution status."""
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NodeResult(BaseModel):
    """Execution result of a node."""
    node_data: BaseNodeData  # Metadata of the node
    status: NodeStatus = NodeStatus.RUNNING
    inputs: dict[str, Any] = Field(default_factory=dict)  # Node input data
    outputs: dict[str, Any] = Field(default_factory=dict)  # Node output data
    latency: float = 0  # Execution time
    error: str = ""  # Error message (if any)
