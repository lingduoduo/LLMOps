#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : decomposition_strategy.py
"""
import os
from operator import itemgetter

import dotenv
import weaviate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_weaviate import WeaviateVectorStore
from weaviate.auth import AuthApiKey

dotenv.load_dotenv()


def format_qa_pair(question: str, answer: str) -> str:
    """Format a question and its answer into a single string."""
    return f"Question: {question}\nAnswer: {answer}\n\n".strip()


# 1. Define the prompt to decompose the main question into sub-questions
decomposition_prompt = ChatPromptTemplate.from_template(
    "You are a helpful AI assistant that generates multiple related sub-questions "
    "for a given input question. The goal is to break down the input into "
    "independently answerable sub-questions or subtasks.\n"
    "Generate exactly 3 search queries related to this question: {question}\n"
    "Separate each query with a newline."
)

# 2. Build the decomposition chain
decomposition_chain = (
        {"question": RunnablePassthrough()}
        | decomposition_prompt
        | ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0)
        | StrOutputParser()
        | (lambda output: output.strip().split("\n"))
)

# 3. Build the vector database and retriever
db = WeaviateVectorStore(
    client=weaviate.connect_to_wcs(
        cluster_url=os.environ.get("WC_CLUSTER_URL"),
        auth_credentials=AuthApiKey(os.environ["WCD_API_KEY"]),
    ),
    index_name="DatasetDemo",
    text_key="text",
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)
retriever = db.as_retriever(search_type="mmr")

# 4. Decompose the main question into sub-questions
main_question = "Which documents discuss LLMOps application configuration?"
sub_questions = decomposition_chain.invoke(main_question)

# 5. Build the iterative QA retrieval chain
qa_prompt = ChatPromptTemplate.from_template(
    """Here is the question to answer:
---
{question}
---

Here are all existing Q&A pairs:
---
{qa_pairs}
---

And here is additional context:
---
{context}
---"""
)
qa_chain = (
        {
            "question": itemgetter("question"),
            "qa_pairs": itemgetter("qa_pairs"),
            "context": itemgetter("question") | retriever,
        }
        | qa_prompt
        | ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0)
        | StrOutputParser()
)

# 6. Iterate over sub-questions to retrieve and answer each
qa_pairs = ""
for sub_question in sub_questions:
    answer = qa_chain.invoke({"question": sub_question, "qa_pairs": qa_pairs})
    qa_pair = format_qa_pair(sub_question, answer)
    qa_pairs += "\n---\n" + qa_pair
    print(f"Sub-question: {sub_question}")
    print(f"Answer: {answer}")
