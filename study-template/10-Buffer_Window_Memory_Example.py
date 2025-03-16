#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.Buffer_Window_Memory_Example.py
"""
from operator import itemgetter

import dotenv
from langchain.memory import ConversationTokenBufferMemory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_openai import ChatOpenAI

# Load environment variables
dotenv.load_dotenv()

# 1. Create a prompt template and memory
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a chatbot developed by OpenAI. Please respond to user questions based on the given context."),
    MessagesPlaceholder("history"),  # 'history' should be a list
    ("human", "{query}"),
])
memory = ConversationTokenBufferMemory(
    return_messages=True,
    input_key="query",
    llm=ChatOpenAI()
)

# 2. Create the large language model
llm = ChatOpenAI(model="gpt-3.5-turbo-16k")

# 3. Build the chain application
chain = RunnablePassthrough.assign(
    history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
) | prompt | llm | StrOutputParser()

# 4. Infinite loop for command-line conversation
while True:
    query = input("Human: ")

    # Exit condition
    if query == "q":
        exit(0)

    # Input to the chain
    chain_input = {"query": query, "language": "English"}

    # Stream the response
    response = chain.stream(chain_input)
    print("AI: ", flush=True, end="")
    output = ""
    for chunk in response:
        output += chunk
        print(chunk, flush=True, end="")

    # Save the conversation context in memory
    memory.save_context(chain_input, {"output": output})
    print("")
    print("History: ", memory.load_memory_variables({}))
