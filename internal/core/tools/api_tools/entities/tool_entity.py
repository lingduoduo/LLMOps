#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : tool_entity.py
"""
from pydantic import BaseModel, Field


class ToolEntity(BaseModel):
    """API tool entity representing configuration details required for creating a LangChain-compatible tool"""
    id: str = Field(default="", description="ID of the API tool provider")
    name: str = Field(default="", description="Name of the API tool")
    url: str = Field(default="", description="URL used to send requests to the API tool")
    method: str = Field(default="get", description="HTTP method used by the API tool")
    description: str = Field(default="", description="Description of the API tool")
    headers: list[dict] = Field(default_factory=list, description="HTTP headers used in the API request")
    parameters: list[dict] = Field(default_factory=list, description="List of parameters required by the API tool")
