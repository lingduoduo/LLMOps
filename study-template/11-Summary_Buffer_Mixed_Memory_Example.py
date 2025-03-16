#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.Summary_Buffer_Mixed_Memory_Example.py
"""
from operator import itemgetter

import dotenv
from langchain.memory import ConversationSummaryBufferMemory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_openai import ChatOpenAI

# Load environment variables
dotenv.load_dotenv()

# 1. Create prompt template and memory
prompt = ChatPromptTemplate.from_messages([
    (
    "system", "You are a chatbot developed by OpenAI. Please respond to user questions based on the provided context."),
    MessagesPlaceholder("history"),  # 'history' should be a list
    ("human", "{query}"),
])
memory = ConversationSummaryBufferMemory(
    max_token_limit=300,  # Limit the maximum token size for memory
    return_messages=True,  # Return messages as part of the memory context
    input_key="query",  # Specify input key
    llm=ChatOpenAI(model="gpt-3.5-turbo-16k"),  # Alternative OpenAI model
)

# 2. Create the large language model
llm = ChatOpenAI(model="gpt-3.5-turbo-16k")  # Alternative model option

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
    chain_input = {"query": query, "language": "Chinese"}

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
