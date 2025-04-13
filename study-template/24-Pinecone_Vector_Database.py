#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.Pinecone_Vector_Database_Usage_Example.py
"""
import dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

dotenv.load_dotenv()

# Initialize the OpenAI embedding model
embedding = OpenAIEmbeddings(model="text-embedding-3-small")

# List of example texts
texts: list = [
    "Benben is a cat who loves to sleep.",
    "I enjoy listening to music at night; it makes me feel relaxed.",
    "The cat is dozing off on the windowsill and looks very cute.",
    "Learning new skills is a goal everyone should pursue.",
    "My favorite food is pasta, especially with tomato sauce.",
    "Last night I had a strange dream where I was flying through space.",
    "My phone suddenly shut down, which made me a bit anxious.",
    "Reading is something I do every day; I find it very fulfilling.",
    "They planned a weekend picnic together, hoping for good weather.",
    "My dog loves chasing balls and looks very happy doing it.",
]

# Metadata corresponding to each text
metadatas: list = [
    {"page": 1},
    {"page": 2},
    {"page": 3},
    {"page": 4},
    {"page": 5},
    {"page": 6, "account_id": 1},
    {"page": 7},
    {"page": 8},
    {"page": 9},
    {"page": 10},
]

# Initialize Pinecone vector store with specified index and namespace
db = PineconeVectorStore(index_name="llmops", embedding=embedding, namespace="dataset")

# Uncomment the line below to add texts and metadata to the vector store
# db.add_texts(texts, metadatas, namespace="dataset")

# Query for similarity search
query = "I have a cat named Benben"
print(db.similarity_search_with_relevance_scores(query,
                                                 filter={"$or": [{"page": 5}, {"account_id": 1}]}
                                                 # filter={"page": {"$gte": 5}}
                                                 ))

id = "75409d98-96d9-4a94-8be8-5138b2f28e8e"
db.delete([id], namespace="dataset")
# pinecone_index = db.get_pinecone_index("llmops")
# pinecone_index.update(id="xxx", values=[], metadata={}, namespace="xxx")
