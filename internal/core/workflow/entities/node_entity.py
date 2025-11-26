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
    """Node type enum."""
    START = "start"
    LLM = "llm"
    TOOL = "tool"
    CODE = "code"
    DATASET_RETRIEVAL = "dataset_retrieval"
    HTTP_REQUEST = "http_request"
    TEMPLATE_TRANSFORM = "template_transform"
    END = "end"


class BaseNodeData(BaseModel):
    """Base node metadata."""

    class Position(BaseModel):
        """Node position model (for UI layout, etc.)."""
        x: float = 0.0
        y: float = 0.0

    class Config:
        # Allow population by field name (useful when aliases are used elsewhere)
        allow_population_by_field_name = True

    # Unique node identifier
    id: UUID

    # Node type
    node_type: NodeType

    # Node title (must be unique within a workflow)
    title: str = ""

    # Node description
    description: str = ""

    # Node position (e.g., canvas coordinates)
    position: Position = Field(default_factory=lambda: {"x": 0, "y": 0})


class NodeStatus(str, Enum):
    """Node execution status."""
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NodeResult(BaseModel):
    """Node execution result."""
    # Node metadata
    node_data: BaseNodeData

    # Execution status
    status: NodeStatus = NodeStatus.RUNNING

    # Input data passed into this node
    inputs: dict[str, Any] = Field(default_factory=dict)

    # Output data produced by this node
    outputs: dict[str, Any] = Field(default_factory=dict)

    # Latency in seconds
    latency: float = 0.0

    # Error message, if any
    error: str = ""
