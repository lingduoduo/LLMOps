#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : multi_query_retriever_example.py
"""
import os

import dotenv
import weaviate
from langchain.retrievers import MultiQueryRetriever
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_weaviate import WeaviateVectorStore
from weaviate.auth import AuthApiKey

# Load environment variables
dotenv.load_dotenv()

# 1. Instantiate a synchronous Weaviate client (positional URL argument)
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

# 3. Create a MultiQueryRetriever using an OpenAI chat model
multi_query_retriever = MultiQueryRetriever.from_llm(
    retriever=retriever,
    llm=ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0),
    include_original=True,
)

# 4. Perform retrieval with multiple generated sub-queries
query = "Which documents cover LLMOps application configurations?"
docs = multi_query_retriever.invoke(query)

# 5. Output retrieved documents and count
print(docs)
print("Number of documents retrieved:", len(docs))
