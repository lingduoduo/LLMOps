#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
@Author  : linghypshen@gmail.com
@File    : RAG_multi_query_fusion_strategy.py
'''

import os
from typing import List

import dotenv
import weaviate
from langchain.load import dumps, loads
from langchain.retrievers import MultiQueryRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_weaviate import WeaviateVectorStore
from weaviate.auth import AuthApiKey

dotenv.load_dotenv()


class RAGFusionRetriever(MultiQueryRetriever):
    '''RAG Multi-Query Fusion Strategy Retriever'''
    k: int = 4

    def retrieve_documents(
            self, queries: List[str], run_manager: CallbackManagerForRetrieverRun
    ) -> List[List[Document]]:
        '''
        Override the document retrieval method to return a nested list of documents for each query.
        '''
        documents = []
        for query in queries:
            docs = self.retriever.invoke(
                query, config={'callbacks': run_manager.get_child()}
            )
            documents.append(docs)
        return documents

    def unique_union(self, documents: List[List[Document]]) -> List[Document]:
        '''
        Deduplicate and fuse the retrieved documents using the Reciprocal Rank Fusion (RRF) algorithm.
        Args:
            documents (List[List[Document]]): A nested list of document lists from multiple queries.
        Returns:
            List[Document]: A list of top k fused documents.
        '''
        # 1. Define a dictionary to store each document's cumulative score
        fused_result = {}

        # 2. Iterate through each list of documents
        for docs in documents:
            for rank, doc in enumerate(docs):
                # 3. Convert the Document instance to a string for hashing
                doc_str = dumps(doc)
                # 4. Initialize score if not already present
                if doc_str not in fused_result:
                    fused_result[doc_str] = 0
                # 5. Add the RRF score component
                fused_result[doc_str] += 1 / (rank + 60)

        # 6. Sort the documents by descending score and select top k
        reranked_results = [
            (loads(doc_str), score)
            for doc_str, score in sorted(fused_result.items(), key=lambda x: x[1], reverse=True)
        ]

        return [item[0] for item in reranked_results[:self.k]]


# Build the vector database and base retriever
db = WeaviateVectorStore(
    client=weaviate.connect_to_wcs(
        cluster_url=os.environ.get("WC_CLUSTER_URL"),
        auth_credentials=AuthApiKey(os.environ["WCD_API_KEY"]),
    ),
    index_name='DatasetDemo',
    text_key='text',
    embedding=OpenAIEmbeddings(model='text-embedding-3-small'),
)
retriever = db.as_retriever(search_type='mmr')

# Initialize the RAG fusion retriever with an LLM
rag_fusion_retriever = RAGFusionRetriever.from_llm(
    retriever=retriever,
    llm=ChatOpenAI(model='gpt-3.5-turbo-16k', temperature=0),
)

# Perform retrieval for an English query
docs = rag_fusion_retriever.invoke('Which documents discuss LLMOps application configuration?')

print(docs)
print(len(docs))
