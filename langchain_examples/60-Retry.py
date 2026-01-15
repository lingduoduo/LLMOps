#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/7/12 9:51
@File    : 1.error_handling.py
"""
from typing import Any

import dotenv
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()


@tool
def complex_tool(int_arg: int, float_arg: float, dict_arg: dict) -> int:
    """Use a complex tool to perform complex calculation operations"""
    return int_arg * float_arg


def try_except_tool(tool_args: dict, config: RunnableConfig) -> Any:
    try:
        return complex_tool.invoke(tool_args, config=config)
    except Exception as e:
        return f"An error was raised when calling the tool with the following arguments:\n\n{tool_args}\n\nError details:\n\n{type(e)}: {e}"


# 1. Create the large language model and bind the tool
llm = ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0)
llm_with_tools = llm.bind_tools([complex_tool])

# 2. Create the chain and execute the tool
chain = llm_with_tools | (lambda msg: msg.tool_calls[0]["args"]) | try_except_tool

# 3. Invoke the chain
print(chain.invoke("Use the complex tool with parameters 5 and 2.1"))

print("----------------------------------------------------------")

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/7/12 10:17
@File    : 2.fallback_handling_strategy.py
"""
import dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()


@tool
def complex_tool(int_arg: int, float_arg: float, dict_arg: dict) -> int:
    """Use a complex tool to perform complex calculation operations"""
    return int_arg * float_arg


# 1. Create the large language model and bind the tool
llm = ChatOpenAI(model="gpt-3.5-turbo-16k").bind_tools([complex_tool])
better_llm = ChatOpenAI(model="gpt-4o").bind_tools([complex_tool])

# 2. Create the chain and execute the tool
better_chain = (better_llm | (lambda msg: msg.tool_calls[0]["args"]) | complex_tool)
chain = (llm | (lambda msg: msg.tool_calls[0]["args"]) | complex_tool).with_fallbacks([better_chain])

# 3. Invoke the chain
print(chain.invoke("Use the complex tool with parameters 5 and 2.1 — don't forget the dict_arg parameter."))

print("----------------------------------------------------------")

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/7/12 10:24
@File    : 3.retry_with_error_info.py
"""
from typing import Any

import dotenv
from langchain_core.messages import ToolCall, AIMessage, ToolMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()


class CustomToolException(Exception):
    def __init__(self, tool_call: ToolCall, exception: Exception) -> None:
        super().__init__()
        self.tool_call = tool_call
        self.exception = exception


@tool
def complex_tool(int_arg: int, float_arg: float, dict_arg: dict) -> int:
    """Use a complex tool to perform complex calculations"""
    return int_arg * float_arg


def tool_custom_exception(msg: AIMessage, config: RunnableConfig) -> Any:
    try:
        return complex_tool.invoke(msg.tool_calls[0]["args"], config=config)
    except Exception as e:
        raise CustomToolException(msg.tool_calls[0], e)


def exception_to_messages(inputs: dict) -> dict:
    # 1. Extract exception info from inputs
    exception = inputs.pop("exception")
    # 2. Build placeholder message list based on exception details
    messages = [
        AIMessage(content="", tool_calls=[exception.tool_call]),
        ToolMessage(tool_call_id=exception.tool_call["id"], content=str(exception.exception)),
        HumanMessage(
            content="The last tool call triggered an exception. Please retry with corrected parameters, and avoid repeating the same mistake."),
    ]
    inputs["last_output"] = messages
    return inputs


# 1. Create prompt
prompt = ChatPromptTemplate.from_messages([
    ("human", "{query}"),
    ("placeholder", "{last_output}")
])

# 2. Create the language model and bind the tool
llm = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(
    tools=[complex_tool], tool_choice="complex_tool",
)

# 3. Create the chain and handle tool execution
chain = prompt | llm | tool_custom_exception
self_correcting_chain = chain.with_fallbacks(
    [exception_to_messages | chain], exception_key="exception"
)

# 4. Invoke the self-correcting chain to complete the task
print(self_correcting_chain.invoke({"query": "Use the complex tool with parameters 5 and 2.1"}))
