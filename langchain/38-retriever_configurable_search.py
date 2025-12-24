#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypsehn@gmail.com
@File    : retriever_configurable_search_example.py
"""
import os

import dotenv
import weaviate
from langchain_core.runnables import ConfigurableField
from langchain_openai import OpenAIEmbeddings
from langchain_weaviate import WeaviateVectorStore
from weaviate.auth import AuthApiKey

# Load environment variables
dotenv.load_dotenv()

# 1. Initialize Weaviate vector store
db = WeaviateVectorStore(
    client=weaviate.connect_to_wcs(
        cluster_url=os.environ.get("WC_CLUSTER_URL"),
        auth_credentials=AuthApiKey(os.environ["WCD_API_KEY"]),
    ),
    index_name="DatasetDemo",
    text_key="text",
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)

# 2. Create retriever with configurable fields for search type and parameters
retriever = db.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"k": 10, "score_threshold": 0.5},
).configurable_fields(
    search_type=ConfigurableField(id="db_search_type"),
    search_kwargs=ConfigurableField(id="db_search_kwargs"),
)

# 3. Override configuration at runtime for MMR search and return 4 results
query = "What API configuration options are available for the application?"
mmr_results = retriever.with_config(
    configurable={
        "db_search_type": "mmr",
        "db_search_kwargs": {"k": 4},
    }
).invoke(query)

# 4. Output the results
print("MMR Search results:", mmr_results)
print("Number of results:", len(mmr_results))

# Print first 20 characters of the top two documents
print(mmr_results[0].page_content[:20])
print(mmr_results[1].page_content[:20])
