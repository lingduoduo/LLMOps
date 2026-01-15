#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshe@gmail.com
@File    : 1.LLM_structured_output.py
"""
import dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()


class QAExtra(BaseModel):
    """A Q&A key-value pair structure for hypothetical questions and their answers"""
    question: str = Field(description="Hypothetical question")
    answer: str = Field(description="Answer to the hypothetical question")


llm = ChatOpenAI(model="gpt-4o")
structured_llm = llm.with_structured_output(QAExtra, method="json_mode")

prompt = ChatPromptTemplate.from_messages([
    ("system", "Extract a hypothetical question and its answer from the user query. "
               "Respond in JSON format with `question` and `answer` fields."),
    ("human", "{query}")
])

chain = {"query": RunnablePassthrough()} | prompt | structured_llm

print(chain.invoke("My name is Ling, and I live in New York."))
