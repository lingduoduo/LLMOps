#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.Entity_Memory_Component_Example.py
"""
import dotenv
from langchain.chains.conversation.base import ConversationChain
from langchain.memory import ConversationEntityMemory
from langchain.memory.prompt import ENTITY_MEMORY_CONVERSATION_TEMPLATE
from langchain_openai import ChatOpenAI

# Load environment variables
dotenv.load_dotenv()

# Initialize the language model
llm = ChatOpenAI(model="gpt-4o", temperature=0)  # Alternative OpenAI model

# Create a conversation chain with entity memory
# Create a conversation chain with entity memory
chain = ConversationChain(
    llm=llm,
    prompt=ENTITY_MEMORY_CONVERSATION_TEMPLATE,  # Uses a template designed for entity memory
    memory=ConversationEntityMemory(llm=llm),  # Entity memory to track and recall key facts
)

# Simulate conversation
print(chain.invoke({"input": "Hello, I'm Ling. I'm currently learning LangChain."}))
print(chain.invoke({"input": "My favorite programming language is Python."}))
print(chain.invoke({"input": "I live in United States."}))

# Query the stored entities from the conversation memory
res = chain.memory.entity_store.store
print(res)
