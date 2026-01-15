#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.delete_and_update_message_example.py
"""

from typing import Any

import dotenv
from langchain_core.messages import HumanMessage, AIMessage, trim_messages
from langchain_core.messages import RemoveMessage  # <- Add AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import MessagesState, StateGraph

# Load environment variables
dotenv.load_dotenv()

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o-mini")


def chatbot(state: MessagesState, config: RunnableConfig) -> Any:
    """Chatbot node: generates an AI message in response to the user's message."""
    return {"messages": [llm.invoke(state["messages"])]}


def delete_human_message(state: MessagesState, config: RunnableConfig) -> Any:
    """Delete the human message from the state."""
    human_message = state["messages"][0]
    return {"messages": [RemoveMessage(id=human_message.id)]}


def update_ai_message(state: MessagesState, config: RunnableConfig) -> Any:
    """Update the AI message by prepending a custom prefix."""
    ai_message = state["messages"][-1]
    return {"messages": [AIMessage(id=ai_message.id, content="Updated AI message: " + ai_message.content)]}


# 1. Create the graph builder
graph_builder = StateGraph(MessagesState)

# 2. Add nodes
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("delete_human_message", delete_human_message)
graph_builder.add_node("update_ai_message", update_ai_message)

# 3. Add edges between nodes
graph_builder.set_entry_point("chatbot")
graph_builder.add_edge("chatbot", "delete_human_message")
graph_builder.add_edge("delete_human_message", "update_ai_message")
graph_builder.set_finish_point("update_ai_message")

# 4. Compile the graph
graph = graph_builder.compile()

# 5. Invoke the graph
print(graph.invoke({"messages": [("human", "Hello, who are you?")]}))

print("================================================================")

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 2.trim_messages_example.py
"""

# Load environment variables
dotenv.load_dotenv()

# Original conversation history
messages = [
    HumanMessage(content="Hi, my name is Ling. I Live in New York. What do you like?"),
    AIMessage([
        {"type": "text",
         "text": "Hi Ling! I'm interested in lots of topics, like exploring new knowledge and helping solve problems. Do you prefer swimming or basketball?"},
        {
            "type": "text",
            "text": "Hi Ling! I enjoy discussing all kinds of topics and helping answer questions. You seem to enjoy both swimming and basketball—do you have a favorite sport or athlete?"
        },
    ]),
    HumanMessage(content="If I want to learn about astrophysics, can you give me some advice?"),
    AIMessage(
        content="Absolutely! You can start with the basics of astronomy and physics, then gradually dive deeper into specific astrophysics topics. Read books like *The Structure of the Universe* or *The Secret of Gravity*, and check out some great astrophysics lectures or courses. What area are you most curious about?"
    ),
]

# Initialize the language model
llm = ChatOpenAI(model="gpt-4o-mini")

# Trim the conversation to fit within 80 tokens
trimmed_messages = trim_messages(
    messages,
    max_tokens=80,
    token_counter=llm,
    # strategy="first",        # Trim from the beginning
    end_on="human",  # Stop trimming after the last human message
    allow_partial=False,  # Don't allow partial messages
    text_splitter=RecursiveCharacterTextSplitter(),
)

# Display the trimmed result
print(trimmed_messages)
