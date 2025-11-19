#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : current_time.py
"""
from datetime import datetime
from typing import Any

from langchain_core.tools import BaseTool


class CurrentTimeTool(BaseTool):
    """A tool for retrieving the current time."""
    name = "current_time"
    description = "A tool for retrieving the current time."

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Get the current system time, format it, and return it."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")


def current_time(**kwargs) -> BaseTool:
    """Return a LangChain tool that provides the current time."""
    return CurrentTimeTool()
