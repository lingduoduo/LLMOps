#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.ConditionalEdge_Loop_ToolCallingAgent.py
"""

import json
from typing import TypedDict, Annotated, Any, Literal

import dotenv
from langchain_community.tools import GoogleSerperRun
from langchain_community.tools.openai_dalle_image_generation import OpenAIDALLEImageGenerationTool
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.messages import ToolMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# Load environment variables
dotenv.load_dotenv()


# Define schemas for each tool
class GoogleSerperArgsSchema(BaseModel):
    query: str = Field(description="Query string for executing a Google search.")


class DallEArgsSchema(BaseModel):
    query: str = Field(description="Text prompt used to generate an image.")


# 1. Define tools
google_serper = GoogleSerperRun(
    name="google_serper",
    description=(
        "A low-cost Google Search API. "
        "Use this tool to answer questions about current events. "
        "The input should be a search query."
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


# Define the graph state
class State(TypedDict):
    messages: Annotated[list, add_messages]


# Bind LLM with tool calling capability
llm = ChatOpenAI(model="gpt-4o-mini")
llm_with_tools = llm.bind_tools(tools)


# Chat node
def chatbot(state: State, config: dict) -> Any:
    """LLM response node"""
    ai_message = llm_with_tools.invoke(state["messages"])
    return {"messages": [ai_message]}


# Tool executor node
def tool_executor(state: State, config: dict) -> Any:
    """Tool execution node"""
    tool_calls = state["messages"][-1].tool_calls
    tools_by_name = {tool.name: tool for tool in tools}

    messages = []
    for tool_call in tool_calls:
        tool = tools_by_name[tool_call["name"]]
        messages.append(ToolMessage(
            tool_call_id=tool_call["id"],
            content=json.dumps(tool.invoke(tool_call["args"])),
            name=tool_call["name"]
        ))

    return {"messages": messages}


# Router node
def route(state: State, config: dict) -> Literal["tool_executor", "__end__"]:
    """Route node to determine the next step"""
    ai_message = state["messages"][-1]
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tool_executor"
    return END


# 1. Create the graph
graph_builder = StateGraph(State)

# 2. Add nodes
graph_builder.add_node("llm", chatbot)
graph_builder.add_node("tool_executor", tool_executor)

# 3. Add edges
graph_builder.set_entry_point("llm")
graph_builder.add_conditional_edges("llm", route)
graph_builder.add_edge("tool_executor", "llm")

# 4. Compile the graph into a runnable object
graph = graph_builder.compile()

# 5. Run the graph
state = graph.invoke({"messages": [("human", "What were the top performance AI models?")]})

# 6. Print output
for message in state["messages"]:
    print("Message type:", message.type)
    if hasattr(message, "tool_calls") and len(message.tool_calls) > 0:
        print("Tool call arguments:", message.tool_calls)
    print("Message content:", message.content)
    print("=====================================")

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/7/15 11:42
@File    : 2.parallel_nodes.py
"""

from typing import Any
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.message import StateGraph, MessagesState

# Initialize a state graph with MessagesState
graph_builder = StateGraph(MessagesState)


# Node: chatbot response
def chatbot(state: MessagesState, config: dict) -> Any:
    return {"messages": [AIMessage(content="Hello, I am a chatbot developed by OpenAI.")]}


# Node: parallel branch 1
def parallel1(state: MessagesState, config: dict) -> Any:
    print("Parallel Branch 1: ", state)
    return {"messages": [HumanMessage(content="This is the parallel1 function.")]}


# Node: parallel branch 2
def parallel2(state: MessagesState, config: dict) -> Any:
    print("Parallel Branch 2: ", state)
    return {"messages": [HumanMessage(content="This is the parallel2 function.")]}


# Node: chat end
def chat_end(state: MessagesState, config: dict) -> Any:
    print("Chat End: ", state)
    return {"messages": [HumanMessage(content="This is the chat end function.")]}


# Build the graph structure
graph_builder.add_node("chat_bot", chatbot)
graph_builder.add_node("parallel1", parallel1)
graph_builder.add_node("parallel2", parallel2)
graph_builder.add_node("chat_end", chat_end)

# Entry and exit points
graph_builder.set_entry_point("chat_bot")
graph_builder.set_finish_point("chat_end")

# Add edges
graph_builder.add_edge("chat_bot", "parallel1")
graph_builder.add_edge("chat_bot", "parallel2")
graph_builder.add_edge("parallel2", "chat_end")

# Compile and execute the graph
graph = graph_builder.compile()
print(graph.invoke({"messages": [HumanMessage(content="Hello, who are you?")]}))
