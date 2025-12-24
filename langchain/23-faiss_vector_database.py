#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.faiss_vector_database_example.py
"""
import os

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import dotenv

# Load environment variables
dotenv.load_dotenv()

import dotenv
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

dotenv.load_dotenv()

embedding = OpenAIEmbeddings(model="text-embedding-3-small")

db = FAISS.from_texts(texts=[
    "Nana is a cat who loves to sleep.",
    "I enjoy listening to music at night; it makes me feel relaxed.",
    "The cat climbed onto the windowsill and looked very cute.",
    "Learning new skills is a goal everyone should pursue.",
    "My favorite food is Italian, especially tomato pasta.",
    "I had a strange dream last night where I was flying in space.",
    "My phone suddenly crashed, which made me a little anxious.",
    "Reading is something I do every day, and I find it very fulfilling.",
    "We went camping together over the weekend. I hope the weather stays nice.",
    "My dog chased the ball happily; he looked really joyful.",
], embedding=embedding,
    relevance_score_fn=lambda distance: 1.0 / (1.0 + distance),
)
print(db.index.ntotal)
print(db.similarity_search_with_score("I adopted a cat and named it Nana."))

db.save_local("./vector-store/")

# Load FAISS vector store from local directory
db = FAISS.load_local("./vector-store/",
                      embedding, allow_dangerous_deserialization=True)

# Perform similarity search with score
print(db.similarity_search_with_score("I have a cat named Benben."))
