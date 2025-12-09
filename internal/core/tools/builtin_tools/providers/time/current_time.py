#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : current_time.py
"""
from datetime import datetime
from typing import Any, Type

from langchain_core.pydantic_v1 import BaseModel
from langchain_core.tools import BaseTool


class CurrentTimeTool(BaseTool):
    """A tool for retrieving the current system time."""
    name = "current_time"
    description = "A tool that returns the current system time."
    args_schema: Type[BaseModel] = BaseModel

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Retrieve and return the current system time in a formatted string."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")


def current_time(**kwargs) -> BaseTool:
    """Return the LangChain tool instance for fetching the current time."""
    return CurrentTimeTool()
