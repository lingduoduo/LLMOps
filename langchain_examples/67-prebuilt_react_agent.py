#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.prebuilt_react_agent.py
"""
import dotenv
from langchain_community.tools import GoogleSerperRun
from langchain_community.tools.openai_dalle_image_generation import OpenAIDALLEImageGenerationTool
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

dotenv.load_dotenv()


class GoogleSerperArgsSchema(BaseModel):
    query: str = Field(description="The query string to execute a Google search.")


class DallEArgsSchema(BaseModel):
    query: str = Field(description="The input should be a text prompt to generate an image.")


# 1. Define tools and tool list
google_serper = GoogleSerperRun(
    name="google_serper",
    description=(
        "A low-cost Google search API. "
        "You can use this tool when you need to answer questions about current events. "
        "The input to this tool is a search query string."
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

# 2. Create a large language model
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 3. Create a ReACT agent using the prebuilt function
agent = create_react_agent(model=model, tools=tools)

# 4. Invoke the agent and print the output
inputs = {"messages": [("human", "Please help me draw an image of a shark flying in the sky")]}

# for chunk in agent.stream(inputs, stream_mode="values"):
#     print(chunk["messages"][-1].pretty_print())

for chunk in agent.stream(inputs, stream_mode="updates"):
    print(chunk)
