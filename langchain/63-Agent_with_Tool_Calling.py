#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/7/14 21:31
@File    : 1.Agent_with_Tool_Calling.py
"""
import dotenv
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_community.tools import GoogleSerperRun
from langchain_community.tools.openai_dalle_image_generation import OpenAIDALLEImageGenerationTool
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI

# Load environment variables from .env file
dotenv.load_dotenv()


# Define argument schema for Google Search
class GoogleSerperArgsSchema(BaseModel):
    query: str = Field(description="The query string used to perform a Google search")


# Define argument schema for DALL·E image generation
class DallEArgsSchema(BaseModel):
    query: str = Field(description="The input should be a text prompt to generate an image")


# 1. Define tools and tool list
google_serper = GoogleSerperRun(
    name="google_serper",
    description=(
        "A low-cost Google Search API. "
        "Use this tool when you need to answer questions about current events. "
        "The input should be a search query."
    ),
    args_schema=GoogleSerperArgsSchema,
    api_wrapper=GoogleSerperAPIWrapper(),
)

dalle = OpenAIDALLEImageGenerationTool(
    name="openai_dalle",
    api_wrapper=DallEAPIWrapper(model="dall-e-3"),
    args_schema=DallEArgsSchema
)

tools = [google_serper, dalle]

# 2. Define prompt template for tool-calling agent
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a chatbot developed by OpenAI, skilled at helping users solve problems."),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# 3. Create the language model
llm = ChatOpenAI(model="gpt-4o-mini")

# 4. Create the agent and agent executor
agent = create_tool_calling_agent(
    prompt=prompt,
    llm=llm,
    tools=tools,
)

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 5. Invoke the agent with an image generation request
# print(agent_executor.invoke({"input": "What is the record of marathon"}))

print(agent_executor.invoke({"input": "Please draw an image of an elderly man climbing a mountain. "}))
