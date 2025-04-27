#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.hybrid_doc_doc_retrieval.py
"""
import os
from typing import List

import dotenv
import weaviate
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_weaviate import WeaviateVectorStore
from weaviate.auth import AuthApiKey

dotenv.load_dotenv()


class HyDERetriever(BaseRetriever):
    """A HyDE hybrid strategy retriever that synthesizes a hypothetical document before retrieval."""
    retriever: BaseRetriever
    llm: BaseLanguageModel

    def _get_relevant_documents(
            self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """Performs HyDE: generates a hypothetical document to enhance retrieval for the given query."""
        # 1. Build the prompt that asks the model to write a scientific-style paper
        prompt = ChatPromptTemplate.from_template(
            "Please write a scientific paper to answer the following question.\n"
            "Question: {question}\n"
            "Paper: "
        )

        # 2. Create the HyDE chain: synthesize a document then retrieve
        chain = (
                {"question": RunnablePassthrough()}
                | prompt
                | self.llm
                | StrOutputParser()
                | self.retriever
        )

        return chain.invoke(query)


# 1. Initialize the vector store and base retriever
db = WeaviateVectorStore(
    client=weaviate.connect_to_wcs(
        cluster_url=os.environ.get("WC_CLUSTER_URL"),
        auth_credentials=AuthApiKey(os.environ["WCD_API_KEY"]),
    ),
    index_name="DatasetDemo",
    text_key="text",
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)
base_retriever = db.as_retriever(search_type="mmr")

# 2. Instantiate the HyDE retriever
hyde_retriever = HyDERetriever(
    retriever=base_retriever,
    llm=ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0),
)

# 3. Retrieve documents using HyDE
documents = hyde_retriever.invoke(
    "What documentation exists for configuring LLMOps applications?"
)
print(documents)
print(len(documents))
