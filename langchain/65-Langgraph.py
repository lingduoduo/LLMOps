#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.basic_langgraph_example.py
"""
from typing import TypedDict, Annotated, Any

import dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

dotenv.load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini")


# 1. Create a state graph and define State as the state data structure
class State(TypedDict):
    """State data for the graph structure"""
    messages: Annotated[list, add_messages]
    use_name: str


def chatbot(state: State, config: dict) -> Any:
    """Chatbot node that uses the LLM to generate content from the list of messages"""
    ai_message = llm.invoke(state["messages"])
    return {"messages": [ai_message], "use_name": "chatbot"}


graph_builder = StateGraph(State)

# 2. Add nodes
graph_builder.add_node("llm", chatbot)

# 3. Add edges
graph_builder.add_edge(START, "llm")
graph_builder.add_edge("llm", END)

# 4. Compile the graph into a Runnable component
graph = graph_builder.compile()

# 5. Invoke the graph application
print(graph.invoke(
    {"messages": [("human", "Hello, who are you? My name is Ling, and I live in New York")], "use_name": "graph"}))
