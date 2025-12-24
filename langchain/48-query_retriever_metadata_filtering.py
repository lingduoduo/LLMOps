# #!/usr/bin/env python
# # -*- coding: utf-8 -*-
# """
# @Author  : linghypshen@gmail.com
# @File    : 10.self_query_retriever_metadata_filtering.py
# """

import os

import dotenv
import weaviate
# from langchain.chains.query_constructor.schema import AttributeInfo
# from langchain.retrievers.self_query.base import SelfQueryRetriever
# # from langchain_weaviate import WeaviateVectorStore
# from langchain_community.vectorstores import Weaviate
# from langchain_core.documents import Document
# from langchain_openai import ChatOpenAI
# from langchain_openai import OpenAIEmbeddings
from weaviate.auth import AuthApiKey

#
# Load environment variables
dotenv.load_dotenv()
#
# # 1. Build a list of documents and upload them to Weaviate
# documents = [
#     Document(
#         page_content="The Shawshank Redemption",
#         metadata={"year": 1994, "rating": 9.7, "director": "Frank Darabont"},
#     ),
#     Document(
#         page_content="Farewell My Concubine",
#         metadata={"year": 1993, "rating": 9.6, "director": "Chen Kaige"},
#     ),
#     Document(
#         page_content="Forrest Gump",
#         metadata={"year": 1994, "rating": 9.5, "director": "Robert Zemeckis"},
#     ),
#     Document(
#         page_content="Titanic",
#         metadata={"year": 1997, "rating": 9.5, "director": "James Cameron"},
#     ),
#     Document(
#         page_content="Spirited Away",
#         metadata={"year": 2001, "rating": 9.4, "director": "Hayao Miyazaki"},
#     ),
#     Document(
#         page_content="Interstellar",
#         metadata={"year": 2014, "rating": 9.4, "director": "Christopher Nolan"},
#     ),
#     Document(
#         page_content="Hachi: A Dog's Tale",
#         metadata={"year": 2009, "rating": 9.4, "director": "Lasse Hallström"},
#     ),
#     Document(
#         page_content="3 Idiots",
#         metadata={"year": 2009, "rating": 9.2, "director": "Rajkumar Hirani"},
#     ),
#     Document(
#         page_content="Zootopia",
#         metadata={"year": 2016, "rating": 9.2, "director": "Byron Howard"},
#     ),
#     Document(
#         page_content="Infernal Affairs",
#         metadata={"year": 2002, "rating": 9.3, "director": "Andrew Lau"},
#     ),
# ]
#
# # Initialize Weaviate client and vector store
client = weaviate.connect_to_wcs(
    cluster_url=os.environ.get("WC_CLUSTER_URL"),
    auth_credentials=AuthApiKey(os.environ["WCD_API_KEY"]),
)
#
# db = Weaviate(
#     client=client,
#     index_name="Dataset",
#     text_key="text",
#     embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
# )
# retriever = db.as_retriever()
# # To add documents to Weaviate, uncomment the following line:
# # db.add_documents(documents)
#
# # 2. Perform a basic similarity search without filters
# metadata_filed_info = [
#     AttributeInfo(name="year", description="year", type="integer"),
#     AttributeInfo(name="rating", description="rating", type="float"),
#     AttributeInfo(name="director", description="director", type="string"),
# ]
#
# self_query_retriever = SelfQueryRetriever.from_llm(
#     llm=ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0),
#     vectorstore=db,
#     document_contents="name",
#     metadata_field_info=metadata_filed_info,
#     enable_limit=True,
# )
# docs = self_query_retriever.invoke("search for movies rating less than 90")
# print(docs)
# print(len(docs))
# print("===================")
# base_docs = retriever.invoke("search for movies rating less than 90")
# print(base_docs)
# print(len(base_docs))
#
# # Close the Weaviate client to avoid resource warnings
# client.close()
#
