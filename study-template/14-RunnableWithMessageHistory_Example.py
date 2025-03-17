#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.RunnableWithMessageHistory_Example.py
"""
import dotenv
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI

# Load environment variables
dotenv.load_dotenv()

# 1. Define the history storage
store = {}


# 2. Factory function to retrieve chat history for a given session
def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = FileChatMessageHistory(f"chat_history_{session_id}.txt")
    return store[session_id]


# 3. Build the prompt template and language model
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a powerful chatbot. Please respond to user questions based on their requests."),
    MessagesPlaceholder("history"),  # Placeholder for chat history
    ("human", "{query}"),  # User's query
])
llm = ChatOpenAI(model="gpt-3.5-turbo-16k")

# 4. Build the chain
chain = prompt | llm | StrOutputParser()

# 5. Wrap the chain with message history management
with_message_chain = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="query",
    history_messages_key="history",
)

# 6. Interactive loop for conversation
while True:
    query = input("Human: ")

    # Exit condition
    if query == "q":
        exit(0)

    # Run the chain and pass configuration data
    response = with_message_chain.stream(
        {"query": query},
        config={"configurable": {"session_id": "session_id"}}
    )

    # Display AI response
    print("AI: ", flush=True, end="")
    for chunk in response:
        print(chunk, flush=True, end="")
    print("")
