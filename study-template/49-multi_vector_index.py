# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.multi_vector_index_summary_retrieve_original_docs.py
"""
import uuid

import dotenv
from langchain.retrievers import MultiVectorRetriever
from langchain.storage import LocalFileStore
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Load environment variables
dotenv.load_dotenv()

# 1. Create a loader, text splitter, and process the document
loader = UnstructuredFileLoader("./ecommerce_product_data.txt")
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
docs = loader.load_and_split(text_splitter)

# 2. Define a summary generation chain
summary_chain = (
        {"doc": lambda x: x.page_content}
        | ChatPromptTemplate.from_template("Please summarize the following document:\n\n{doc}")
        | ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0)
        | StrOutputParser()
)

# 3. Generate summaries in batch and assign unique IDs
summaries = summary_chain.batch(docs, {"max_concurrency": 5})
doc_ids = [str(uuid.uuid4()) for _ in summaries]

# 4. Build summary documents
summary_docs = [
    Document(page_content=summary, metadata={"doc_id": doc_ids[idx]})
    for idx, summary in enumerate(summaries)
]

# 5. Set up a document database and vector store for embeddings
byte_store = LocalFileStore("./multi-vector")
db = FAISS.from_documents(
    summary_docs,
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)

# 6. Initialize the multi-vector retriever
retriever = MultiVectorRetriever(
    vectorstore=db,
    byte_store=byte_store,
    id_key="doc_id",
)

# 7. Store both the summaries and the original documents in the retriever's store
retriever.docstore.mset(list(zip(doc_ids, docs)))

# 8. Perform a search query
search_results = retriever.invoke("Recommend some Teochew specialties?")
print(search_results)
print(f"Number of results: {len(search_results)}")

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 2.multi_vector_index_hypothetical_query_retrieve_original_docs.py
"""
from typing import List

import dotenv
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI

# Load environment variables
dotenv.load_dotenv()


class HypotheticalQuestions(BaseModel):
    """Generate hypothetical questions."""
    questions: List[str] = Field(
        description="A list of hypothetical questions, each a string",
    )


# 1. Build a prompt that generates hypothetical questions
prompt = ChatPromptTemplate.from_template(
    "Generate a list of 3 hypothetical questions that could be used to explore the following document:\n\n{doc}"
)

# 2. Create the LLM and bind it to the structured output schema
llm = ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0)
structured_llm = llm.with_structured_output(HypotheticalQuestions)

# 3. Assemble the chain
chain = (
        {"doc": lambda x: x.page_content}
        | prompt
        | structured_llm
)

# Invoke the chain on a sample document
hypothetical_questions: HypotheticalQuestions = chain.invoke(
    Document(page_content="My name is Ling, and I enjoy coding.")
)

print(hypothetical_questions)
