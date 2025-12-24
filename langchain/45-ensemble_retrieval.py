#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 7.ensemble_retrieval_example.py
"""
import os

import dotenv
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

os.environ["KMP_DUPLICATE_LIB_OK"] = "True"

dotenv.load_dotenv()

# 1. Create a list of documents
documents = [
    Document(page_content="Benben is a cat who really loves to sleep.", metadata={"page": 1}),
    Document(page_content="I enjoy listening to music at night; it relaxes me.", metadata={"page": 2}),
    Document(page_content="The cat dozes on the windowsill and looks very cute.", metadata={"page": 3}),
    Document(page_content="Learning new skills is a goal everyone should pursue.", metadata={"page": 4}),
    Document(page_content="My favorite food is pasta, especially with tomato sauce.", metadata={"page": 5}),
    Document(page_content="Last night I had a strange dream where I was flying in space.", metadata={"page": 6}),
    Document(page_content="My phone suddenly shut off, making me feel anxious.", metadata={"page": 7}),
    Document(page_content="Reading is something I do every day; it makes me feel fulfilled.", metadata={"page": 8}),
    Document(page_content="They planned a weekend picnic together, hoping for good weather.", metadata={"page": 9}),
    Document(page_content="My dog loves chasing balls and looks very happy.", metadata={"page": 10}),
]

# 2. Build a BM25 keyword retriever
bm25_retriever = BM25Retriever.from_documents(documents)
bm25_retriever.k = 4

# 3. Create a FAISS vector store retriever
faiss_db = FAISS.from_documents(
    documents, embedding=OpenAIEmbeddings(model="text-embedding-3-small")
)
faiss_retriever = faiss_db.as_retriever(search_kwargs={"k": 4})

# 4. Initialize the ensemble retriever
ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, faiss_retriever],
    weights=[0.5, 0.5],
)

# 5. Perform the retrieval
query = "Besides cats, what other pets do you have?"
docs = ensemble_retriever.invoke(query)
print(docs)
print(len(docs))
