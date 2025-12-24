#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.GPT_Model_Bound_Tools.py
"""

import dotenv
from langchain_community.tools import GoogleSerperRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import Field, BaseModel
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()


class GoogleSerperArgsSchema(BaseModel):
    query: str = Field(description="Query string to perform Google search")


# 1. Define tools
google_serper = GoogleSerperRun(
    name="google_serper",
    description=(
        "A low-cost Google search API. "
        "Use this tool when you need to answer questions about current events. "
        "The input to this tool is a search query string."
    ),
    args_schema=GoogleSerperArgsSchema,
    api_wrapper=GoogleSerperAPIWrapper(),
)
tool_dict = {
    google_serper.name: google_serper,
}
tools = [tool for tool in tool_dict.values()]

# 2. Create prompt
prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a chatbot developed by OpenAI. You can help users answer questions and call tools if necessary. "
        "If a question requires multiple tools, please call all tools at once instead of step-by-step."
    ),
    ("human", "{query}"),
])

# 3. Create LLM and bind tools
llm = ChatOpenAI(model="gpt-4o")
llm_with_tool = llm.bind_tools(tools=tools)

# 4. Create runnable chain
chain = {"query": RunnablePassthrough()} | prompt | llm_with_tool

# 5. Invoke chain and get output
query = "What is the current weather in Short Hills, and use the Google search tool."
resp = chain.invoke(query)
tool_calls = resp.tool_calls

# 6. Check if it's a tool call or direct output
if len(tool_calls) <= 0:
    print("Generated content: ", resp.content)
else:
    # 7. Combine history: system, user, and AI messages
    messages = prompt.invoke(query).to_messages()
    messages.append(resp)

    # 8. Loop through all tool calls
    for tool_call in tool_calls:
        tool = tool_dict.get(tool_call.get("name"))  # Get the tool to execute
        print("Executing tool: ", tool.name)
        content = tool.invoke(tool_call.get("args"))  # Result of tool execution
        print("Tool output: ", content)
        tool_call_id = tool_call.get("id")
        messages.append(ToolMessage(
            content=content,
            tool_call_id=tool_call_id,
        ))
    print("Final output: ", llm.invoke(messages).content)
