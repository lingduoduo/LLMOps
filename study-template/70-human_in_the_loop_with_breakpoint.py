#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.human_in_the_loop_with_breakpoint.py
"""

from typing import TypedDict, Annotated, Any, Literal

import dotenv
from langchain_community.tools import GoogleSerperRun
from langchain_community.tools.openai_dalle_image_generation import OpenAIDALLEImageGenerationTool
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# Load environment variables
dotenv.load_dotenv()


# Define schemas for the tools
class GoogleSerperArgsSchema(BaseModel):
    query: str = Field(description="Query string for performing Google search")


class DallEArgsSchema(BaseModel):
    query: str = Field(description="Text prompt to generate an image")


# 1. Define tools
google_serper = GoogleSerperRun(
    name="google_serper",
    description=(
        "A low-cost Google Search API. "
        "Use this tool when you need to answer current event-related questions. "
        "The input should be a search query string."
    ),
    args_schema=GoogleSerperArgsSchema,
    api_wrapper=GoogleSerperAPIWrapper(),
)

dalle = OpenAIDALLEImageGenerationTool(
    name="openai_dalle",
    api_wrapper=DallEAPIWrapper(model="dall-e-3"),
    args_schema=DallEArgsSchema,
)

tools = [google_serper, dalle]


# Define the state structure
class State(TypedDict):
    """Graph state structure represented as a dictionary"""
    messages: Annotated[list, add_messages]


# Bind LLM with tool-calling capability
llm = ChatOpenAI(model="gpt-4o-mini")
llm_with_tools = llm.bind_tools(tools)


def chatbot(state: State, config: dict) -> Any:
    """LLM node that generates a response based on the message state"""
    ai_message = llm_with_tools.invoke(state["messages"])
    return {"messages": [ai_message]}


def route(state: State, config: dict) -> Literal["tools", "__end__"]:
    """Route decision: whether to call tools or end"""
    ai_message = state["messages"][-1]
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tools"
    return END


# 1. Create the state graph
graph_builder = StateGraph(State)

# 2. Add nodes
graph_builder.add_node("llm", chatbot)
graph_builder.add_node("tools", ToolNode(tools=tools))

# 3. Add edges
graph_builder.add_edge(START, "llm")
graph_builder.add_edge("tools", "llm")
graph_builder.add_conditional_edges("llm", route)

# 4. Compile the graph with a breakpoint before the tool step
checkpointer = MemorySaver()
graph = graph_builder.compile(checkpointer=checkpointer, interrupt_before=["tools"])

# 5. First invocation of the graph
config = {"configurable": {"thread_id": 1}}
state = graph.invoke(
    {"messages": [("human", "What are the top 3 results of the 2025 Half Marathon?")]},
    config=config,
)
print(state)

# 6. Human-in-the-loop: ask user whether to proceed with tool execution
if hasattr(state["messages"][-1], "tool_calls") and len(state["messages"][-1].tool_calls) > 0:
    print("Tool is ready to be called:", state["messages"][-1].tool_calls)
    human_input = input("Type 'yes' to execute the tool, or 'no' to stop: ")
    if human_input.lower() == "yes":
        print(graph.invoke(None, config)["messages"][-1].content)
    else:
        print("Graph execution ended.")
