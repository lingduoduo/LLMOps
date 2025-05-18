#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : duckduckgo_search.py
"""
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool

from internal.lib.helper import add_attribute


class DDGInput(BaseModel):
    query: str = Field(description="The search query to execute")


@add_attribute("args_schema", DDGInput)
def duckduckgo_search(**kwargs) -> BaseTool:
    """Return a DuckDuckGo search tool."""
    return DuckDuckGoSearchRun(
        description=(
            "A privacy-focused search tool you can use to look up current events. "
            "The tool accepts a query string as input."
        ),
        args_schema=DDGInput,
    )
