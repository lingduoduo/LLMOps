#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/7/14 21:58
@File    : 1.XMLAgent_Example.py
"""
import dotenv
from langchain.agents import create_xml_agent, AgentExecutor
from langchain_community.tools import GoogleSerperRun
from langchain_community.tools.openai_dalle_image_generation import OpenAIDALLEImageGenerationTool
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI

# Load environment variables from .env file
dotenv.load_dotenv()


# Define input schema for Google Search tool
class GoogleSerperArgsSchema(BaseModel):
    query: str = Field(description="Query string for performing a Google search")


# Define input schema for DALL·E image generation tool
class DallEArgsSchema(BaseModel):
    query: str = Field(description="The input should be a text prompt to generate an image")


# 1. Define tools and tool list
google_serper = GoogleSerperRun(
    name="google_serper",
    description=(
        "A low-cost Google search API. "
        "Use this tool when answering questions about current events. "
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

# 2. Define prompt template for the XML tool-calling agent
prompt = ChatPromptTemplate.from_messages([
    ("human", """You are a helpful assistant. Help the user answer any questions.

You have access to the following tools:

{tools}

In order to use a tool, you can use <tool></tool> and <tool_input></tool_input> tags. You will then get back a response in the form <observation></observation>
For example, if you have a tool called 'search' that could run a Google search, in order to search for the weather in SF you would respond:

<tool>search</tool><tool_input>weather in SF</tool_input>
<observation>64 degrees</observation>

When you are done, respond with a final answer between <final_answer></final_answer>. For example:

<final_answer>The weather in SF is 64 degrees</final_answer>

Begin!

Previous Conversation:
{chat_history}

Question: {input}
{agent_scratchpad}"""),
])

# 3. Create the language model
llm = ChatOpenAI(model="gpt-4o-mini")

# 4. Create the agent and the agent executor
agent = create_xml_agent(
    prompt=prompt,
    llm=llm,
    tools=tools,
)

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 5. Run the agent with a sample input
print(agent_executor.invoke({"input": "What is the world record for marathon?", "chat_history": ""}))
