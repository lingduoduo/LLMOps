#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/7/16 11:09
@File    : 1.conditional_edges_and_loop_tool_agent.py
"""

import dotenv
from langchain_community.tools import GoogleSerperRun
from langchain_community.tools.openai_dalle_image_generation import OpenAIDALLEImageGenerationTool
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

# Load environment variables
dotenv.load_dotenv()


# Define argument schema for Google Search
class GoogleSerperArgsSchema(BaseModel):
    query: str = Field(description="Query string for executing a Google search.")


# Define argument schema for DALL·E image generation
class DallEArgsSchema(BaseModel):
    query: str = Field(description="Text prompt for generating an image.")


# 1. Define tools
google_serper = GoogleSerperRun(
    name="google_serper",
    description=(
        "A low-cost Google Search API. "
        "Use this tool when you need to answer questions about current events. "
        "The input is a search query."
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

# 2. Initialize the language model
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 3. Create the ReACT agent using a prebuilt helper
checkpointer = MemorySaver()
config = {"configurable": {"thread_id": 1}}

agent = create_react_agent(
    model=model,
    tools=tools,
    checkpointer=checkpointer,
)

# 4. First invocation
print(agent.invoke(
    {"messages": [("human", "Hello, my name is Ling. I live in New York. What do you like?")]},
    config=config,
))

# 5. Second invocation to test memory retention
print(agent.invoke(
    {"messages": [("human", "Do you remember my name?")]},
    config={"configurable": {"thread_id": 2}},
))

print(agent.invoke(
    {"messages": [("human", "Do you remember my name?")]},
    config={"configurable": {"thread_id": 1}},
))
