#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/7/13 22:42
@File    : 62-ReACT_Agent.py
"""

import dotenv
from langchain.agents import create_react_agent, AgentExecutor
from langchain_community.tools import GoogleSerperRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import render_text_description_and_args
from langchain_openai import ChatOpenAI

# Load environment variables from .env file (make sure your SERPER_API_KEY is set here)
dotenv.load_dotenv()


# Define the argument schema for the Google search tool
class GoogleSerperArgsSchema(BaseModel):
    query: str = Field(description="The query string for performing a Google search")


# 1. Define the tool and tool list
google_serper = GoogleSerperRun(
    name="google_serper",
    description=(
        "A low-cost Google search API. "
        "You can use this tool when you need to answer questions about current events. "
        "The input should be a search query."
    ),
    args_schema=GoogleSerperArgsSchema,
    api_wrapper=GoogleSerperAPIWrapper(),
)
tools = [google_serper]

# 2. Define the prompt template for the agent
prompt = ChatPromptTemplate.from_template(
    "Answer the following questions as best you can. You have access to the following tools:\n\n"
    "{tools}\n\n"
    "Use the following format:\n\n"
    "Question: the input question you must answer\n"
    "Thought: you should always think about what to do\n"
    "Action: the action to take, should be one of [{tool_names}]\n"
    "Action Input: the input to the action\n"
    "Observation: the result of the action\n"
    "... (this Thought/Action/Action Input/Observation can repeat N times)\n"
    "Thought: I now know the final answer\n"
    "Final Answer: the final answer to the original input question\n\n"
    "Begin!\n\n"
    "Question: {input}\n"
    "Thought:{agent_scratchpad}\n"
    "Remember: Always follow the format exactly. End with 'Final Answer:'."
)

# 3. Create the language model and the agent
llm = ChatOpenAI(model="gpt-4o", temperature=0)

agent = create_react_agent(
    llm=llm,
    prompt=prompt,
    tools=tools,
    tools_renderer=render_text_description_and_args,
)

# 4. Create the agent executor — with error handling enabled
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True  # <-- This allows the agent to retry if format is invalid
)

# 5. Run the agent and retrieve a response
# Use a query that prompts tool use
print(agent_executor.invoke({"input": "What's the latest news on AI research in 2024?"}))
