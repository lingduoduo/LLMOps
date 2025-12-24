#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.DuckDuckGo.py
"""
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.utils.function_calling import convert_to_openai_tool

# Initialize a DuckDuckGo search tool with a description
search = DuckDuckGoSearchRun()
print(search.run("What is latest OpenAI version?"))

# Print out some tool metadata
print("Name:", search.name)
print("Description:", search.description)
print("Arguments:", search.args)
print("Return Directly:", search.return_direct)

# Invoke the search tool with a query about the latest version of LangChain
print(search.invoke("What is the latest version of LangChain?"))
print(convert_to_openai_tool(search))
