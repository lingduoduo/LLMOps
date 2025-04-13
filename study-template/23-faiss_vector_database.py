#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.faiss_vector_database_example.py
"""
import dotenv
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

# Load environment variables
dotenv.load_dotenv()

# Initialize OpenAI embedding model
embedding = OpenAIEmbeddings(model="text-embedding-3-small")

# Load FAISS vector store from local directory
db = FAISS.load_local("./vector-store/", embedding, allow_dangerous_deserialization=True)

# Perform similarity search with score
print(db.similarity_search_with_score("I have a cat named Benben."))
