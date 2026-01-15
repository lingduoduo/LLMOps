#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.multi_agent_with_subgraphs.py
"""

from typing import TypedDict, Any, Annotated

import dotenv
from langchain_community.tools import GoogleSerperRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# Load environment variables
dotenv.load_dotenv()

# Initialize language model
llm = ChatOpenAI(model="gpt-4o-mini")


# Define the schema for the Google search tool
class GoogleSerperArgsSchema(BaseModel):
    query: str = Field(description="Query string to perform a Google search.")


# Define the tool
google_serper = GoogleSerperRun(
    api_wrapper=GoogleSerperAPIWrapper(),
    args_schema=GoogleSerperArgsSchema,
)


# Reducer for merging string fields
def reduce_str(left: str | None, right: str | None) -> str:
    if right is not None and right != "":
        return right
    return left


# Overall agent state
class AgentState(TypedDict):
    query: Annotated[str, reduce_str]  # Original user query
    live_content: Annotated[str, reduce_str]  # Content generated for live streaming
    marketing_content: Annotated[str, reduce_str]  # Content generated for Marketing


# Expanded live agent state with memory
class LiveAgentState(TypedDict):
    query: Annotated[str, reduce_str]
    live_content: Annotated[str, reduce_str]
    marketing_content: Annotated[str, reduce_str]
    messages: Annotated[list, add_messages]


# Marketing agent state (same as top-level agent)
class MarketingAgentState(AgentState):
    pass


# Node: live-streaming copywriter agent
def chatbot_live(state: LiveAgentState, config: RunnableConfig) -> Any:
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a seasoned livestream copywriting expert with 10 years of experience. "
            "Please write a product script based on the user's product description. "
            "If the product is not in your knowledge base, feel free to use a search tool."
        ),
        ("human", "{query}"),
        ("placeholder", "{chat_history}"),
    ])
    chain = prompt | llm.bind_tools([google_serper])
    ai_message = chain.invoke({"query": state["query"], "chat_history": state["messages"]})
    return {
        "messages": [ai_message],
        "live_content": ai_message.content,
    }


# Subgraph 1: livestream agent
live_agent_graph = StateGraph(LiveAgentState)
live_agent_graph.add_node("chatbot_live", chatbot_live)
live_agent_graph.add_node("tools", ToolNode([google_serper]))
live_agent_graph.set_entry_point("chatbot_live")
live_agent_graph.add_conditional_edges("chatbot_live", tools_condition)
live_agent_graph.add_edge("tools", "chatbot_live")


# Node: Marketing content generator
def chatbot_marketing(state: MarketingAgentState, config: RunnableConfig) -> Any:
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a marketing content expert. Please write a fun, engaging post about the given product. "
         "Make sure to use a lively tone and lots of emojis!"),
        ("human", "{query}"),
    ])
    chain = prompt | llm | StrOutputParser()
    return {"marketing_content": chain.invoke({"query": state["query"]})}


# Subgraph 2: marketing agent
maketing_agent_graph = StateGraph(MarketingAgentState)
maketing_agent_graph.add_node("chatbot_marketing", chatbot_marketing)
maketing_agent_graph.set_entry_point("chatbot_marketing")
maketing_agent_graph.set_finish_point("chatbot_marketing")


# Combined parent graph
def parallel_node(state: AgentState, config: RunnableConfig) -> Any:
    return state


agent_graph = StateGraph(AgentState)
agent_graph.add_node("parallel_node", parallel_node)
agent_graph.add_node("live_agent", live_agent_graph.compile())
agent_graph.add_node("marketing_agent", maketing_agent_graph.compile())

agent_graph.set_entry_point("parallel_node")
agent_graph.add_edge("parallel_node", "live_agent")
agent_graph.add_edge("parallel_node", "marketing_agent")
agent_graph.set_finish_point("live_agent")
agent_graph.set_finish_point("marketing_agent")

# Compile the full graph
agent = agent_graph.compile()

# Run the graph
print(agent.invoke({"query": "Short Hills Weather"}))
