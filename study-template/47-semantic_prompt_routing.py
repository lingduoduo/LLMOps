#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 9.semantic_prompt_routing.py
"""
import dotenv
import numpy as np
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

dotenv.load_dotenv()

# 1. Define two different prompt templates (physics template and math template)
physics_template = """You are a very clever physics tutor.
You excel at explaining physics questions in a concise and easy-to-understand way.
When you do not know the answer, you will frankly admit that you do not know.

Here is a question:
{query}"""
math_template = """You are an outstanding mathematician.
You excel at answering math questions.
You are so good because you can break complex problems into multiple smaller steps,
answer those smaller steps, and then combine them back to address the broader problem.

Here is a question:
{query}"""

# 2. Initialize a text embedding model and compute embeddings for the templates
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
prompt_templates = [physics_template, math_template]
prompt_embeddings = np.array(embeddings.embed_documents(prompt_templates))


def prompt_router(input) -> ChatPromptTemplate:
    """Return a different ChatPromptTemplate based on the query by computing cosine similarity."""
    # 1. Compute the embedding vector for the incoming query
    query_embedding = np.array(embeddings.embed_query(input["query"]))

    # 2. Compute cosine similarities manually:
    #    sims[i] = (query_embedding · prompt_embeddings[i]) / (||query_embedding|| * ||prompt_embeddings[i]||)
    dots = prompt_embeddings.dot(query_embedding)
    norms = np.linalg.norm(prompt_embeddings, axis=1) * np.linalg.norm(query_embedding)
    sims = dots / norms
    most_similar = prompt_templates[np.argmax(sims)]

    print("Using math template" if most_similar == math_template else "Using physics template")

    # 3. Build and return the ChatPromptTemplate from the selected template
    return ChatPromptTemplate.from_template(most_similar)


# 3. Assemble the chain with routing logic
chain = (
        {"query": RunnablePassthrough()}
        | RunnableLambda(prompt_router)
        | ChatOpenAI(model="gpt-3.5-turbo-16k")
        | StrOutputParser()
)

# 4. Test the chain
print(chain.invoke("What is a black hole?"))
print("======================")

print(chain.invoke("Can you run 110 * 100?"))
