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

# Load environment variables
dotenv.load_dotenv()


# Define input schema for Google search tool
class GoogleSerperArgsSchema(BaseModel):
    query: str = Field(description="Query string to perform a Google search.")


# Define input schema for DALL·E image generation tool
class DallEArgsSchema(BaseModel):
    query: str = Field(description="Text prompt to generate an image.")


# 1. Define tools and tool list
google_serper = GoogleSerperRun(
    name="google_serper",
    description=(
        "A low-cost Google Search API. "
        "Use this tool when you need to answer questions about current events. "
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

# 2. Create the language model
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 3. Use the prebuilt function to create a ReACT agent
agent = create_react_agent(model=model, tools=tools)

# 4. Invoke the agent and output the result
print(agent.invoke({"messages": [("human", "Please draw a picture of a shark flying in the sky.")]}))
