#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.model_without_function_call_support_example.py
"""
from typing import Any, TypedDict, Dict, Optional

import dotenv
from langchain_community.tools import GoogleSerperRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import Field, BaseModel
from langchain_core.runnables import RunnableConfig, RunnablePassthrough
from langchain_core.tools import render_text_description_and_args
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()


class GoogleSerperArgsSchema(BaseModel):
    query: str = Field(description="The query string for performing a Google search")


class ToolCallRequest(TypedDict):
    name: str
    arguments: Dict[str, Any]


# 1. Define tools
google_serper = GoogleSerperRun(
    name="google_serper",
    description=(
        "A low-cost Google search API. "
        "Use this tool when answering questions about current events. "
        "The input to this tool is a search query string."
    ),
    args_schema=GoogleSerperArgsSchema,
    api_wrapper=GoogleSerperAPIWrapper(),
)
tool_dict = {
    google_serper.name: google_serper,
}
tools = [tool for tool in tool_dict.values()]


def invoke_tool(
        tool_call_request: ToolCallRequest, config: Optional[RunnableConfig] = None,
) -> str:
    """
    Function to perform tool invocation.

    :param tool_call_request: A dictionary containing tool name and arguments. The name must match a registered tool.
    :param config: Optional LangChain RunnableConfig with callbacks, metadata, etc.
    :return: The result of the tool execution.
    """
    name = tool_call_request["name"]
    requested_tool = tool_dict.get(name)
    return requested_tool.invoke(tool_call_request.get("arguments"), config=config)


system_prompt = """You are a chatbot developed by OpenAI and have access to the following tools.
Below are the names and descriptions of each tool:

{rendered_tools}

Based on the user's input, return the name of the tool to use and the input.
Respond with a JSON block containing `name` and `arguments`.
`arguments` should be a dictionary where keys match parameter names and values are the user-supplied inputs.
"""
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{query}")
]).partial(rendered_tools=render_text_description_and_args(tools))

llm = ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0)

chain = prompt | llm | JsonOutputParser() | RunnablePassthrough.assign(output=invoke_tool)

print(chain.invoke({"query": "What is the world record for marathon?"}))
