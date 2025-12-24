#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghuang@gmail.com
@File    : 01.huggingface_local_embedding_example.py
"""
from langchain_huggingface import HuggingFaceEmbeddings

# Load Hugging Face embedding model with local cache
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L12-v2",
    cache_folder="./embeddings/"
)

# Embed a query
query_vector = embeddings.embed_query("Hello, I'm Ling, and I live in New York.")

print(query_vector)
print(len(query_vector))

# import dotenv
# from langchain_huggingface import HuggingFaceEndpointEmbeddings
#
# # Load environment variables from .env file
# dotenv.load_dotenv()
#
# # Use Hugging Face Inference Endpoint to load embedding model
# embeddings = HuggingFaceEndpointEmbeddings(model="sentence-transformers/all-MiniLM-L12-v2")
#
# # Embed a query
# query_vector = embeddings.embed_query("Hello, I'm Ling, and I live in New York.")
#
# print(query_vector)
# print(len(query_vector))
