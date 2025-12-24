#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.RunnableRetryMechanism.py
"""
from langchain_core.runnables import RunnableLambda

counter = -1


def func(x):
    global counter
    counter += 1
    print(f"Current value is {counter=}")
    return x / counter


chain = RunnableLambda(func).with_retry(stop_after_attempt=2)

resp = chain.invoke(2)

print(resp)

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : 2.RunnableFallbackMechanism.py
"""
import dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Load environment variables from a .env file
dotenv.load_dotenv()

# 1. Construct the prompt and LLM, switching the model to gpt-3.5-turbo-18k to induce an error
prompt = ChatPromptTemplate.from_template("{query}")
llm = ChatOpenAI(model="gpt-3.5-turbo-18k").with_fallbacks([])

# 2. Initialize the primary LLM with an invalid model to induce an error
primary_llm = ChatOpenAI(model="gpt-3.5-turbo-18k")

# 3. Initialize the fallback LLM with a valid model
fallback_llm = ChatOpenAI(model="gpt-3.5-turbo")

# 4. Apply the fallback mechanism
llm_with_fallback = primary_llm.with_fallbacks([fallback_llm])

# 5. Build the chain application
chain = prompt | llm_with_fallback

# 6. Invoke the chain and output the result
content = chain.invoke({"query": "Hello, who are you?"})
print(content)
