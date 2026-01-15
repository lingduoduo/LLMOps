#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.bindFunction.py
"""
import dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()

prompt = ChatPromptTemplate.from_messages([
    ("human", "{query}")
])
llm = ChatOpenAI(model="gpt-3.5-turbo")

chain = prompt | llm.bind(model="gpt-4o") | StrOutputParser()

content = chain.invoke({"query": "What's your model？"})

print(content)

import random

from langchain_core.runnables import RunnableLambda


def get_weather(location: str, unit: str, name: str) -> str:
    """Fetch weather information for a given location and temperature unit."""
    print("Location:", location)
    print("Unit:", unit)
    print("Name:", name)
    return f"The weather in {location} is {random.randint(24, 40)} {unit}"


# Create a RunnableLambda with pre-defined parameters for `unit` and `name`
get_weather_runnable = RunnableLambda(get_weather).bind(unit="Celsius", name="Ling")

# Invoke the runnable with the location "Guangzhou"
resp = get_weather_runnable.invoke("New Jersey")

print(resp)
