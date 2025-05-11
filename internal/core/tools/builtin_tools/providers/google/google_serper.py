#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : google_serper.py
"""
from internal.lib.helper import add_attribute
from langchain_community.tools import GoogleSerperRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool


class GoogleSerperArgsSchema(BaseModel):
    """Description of Google Serper API search parameters."""
    query: str = Field(description="The query string to search for.")


@add_attribute("args_schema", GoogleSerperArgsSchema)
def google_serper(**kwargs) -> BaseTool:
    """Google Serp search tool."""
    return GoogleSerperRun(
        name="google_serper",
        description=(
            "This is a low-cost Google Search API. "
            "Use this tool when you need to search for current events; "
            "the input should be a query string."
        ),
        args_schema=GoogleSerperArgsSchema,
        api_wrapper=GoogleSerperAPIWrapper(),
    )
