#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : tool_entity.py
"""
from enum import Enum
from typing import Optional, Any

from pydantic import BaseModel, Field


class ToolParamType(str, Enum):
    """Enum class for tool parameter types"""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"


class ToolParam(BaseModel):
    """Tool parameter definition"""
    name: str  # The actual name of the parameter
    label: str  # The display label of the parameter
    type: ToolParamType  # The type of the parameter
    required: bool = False  # Whether it is required
    default: Optional[Any] = None  # Default value
    min: Optional[float] = None  # Minimum value
    max: Optional[float] = None  # Maximum value
    options: list[dict[str, Any]] = Field(default_factory=list)  # List of dropdown menu options


class ToolEntity(BaseModel):
    """Tool entity class that stores information mapped from the corresponding tool's YAML file"""
    name: str  # Tool name
    label: str  # Tool label
    description: str  # Tool description
    params: list[ToolParam] = Field(default_factory=list)  # Information about the tool's parameters
