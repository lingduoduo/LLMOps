# #!/usr/bin/env python
# # -*- coding: utf-8 -*-
# """
# @Author  : linghypshen@gmail.com
# @File    : 1.normalize_function_callback_output.py
# """
from typing import Literal

import dotenv
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()


class RouteQuery(BaseModel):
    """Map a user query to the appropriate data source."""
    datasource: Literal["python_docs", "js_docs", "golang_docs"] = Field(
        description="Based on the user's question, choose the most relevant data source to answer it."
    )


# 1. Create a language model instance with structured output binding
llm = ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0)
structured_llm = llm.with_structured_output(RouteQuery)

# 2. Build a question
question = """Why is the following code not working? Please help me check it:

var a = "123"
"""
res: RouteQuery = structured_llm.invoke(question)

print(res)
print(type(res))
print(res.datasource)

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 8.routing_based_on_logic_and_semantics.py
"""
from typing import Literal

import dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()


class RouteQuery(BaseModel):
    """Map a user query to the most relevant data source."""
    datasource: Literal["python_docs", "js_docs", "golang_docs"] = Field(
        description="Select the most relevant data source to answer the user's question based on the given query."
    )


def choose_route(result: RouteQuery) -> str:
    """Choose a retriever based on the routing result."""
    if "python_docs" in result.datasource:
        return "chain in python_docs"
    elif "js_docs" in result.datasource:
        return "chain in js_docs"
    else:
        return "chain in golang_docs"


# 1. Build the language model and enable structured output
llm = ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0)
structured_llm = llm.with_structured_output(RouteQuery)

# 2. Create the routing logic chain
prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an expert at routing user questions to the appropriate data source.\nPlease route the question to the relevant data source based on the programming language involved."),
    ("human", "{question}")
])
router = {"question": RunnablePassthrough()} | prompt | structured_llm | choose_route

# 3. Invoke a sample question to test the routing
question = """Why is the following code not working? Please help me check it:

from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages(["human", "speak in {language}"])
prompt.invoke("Chinese")"""

# 4. Route to the selected data source
print(router.invoke(question))
