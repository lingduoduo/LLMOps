#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.Few_example_prompt_template.py
"""
import dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()

# 1. Build the example prompt template and example pairs
example_prompt = ChatPromptTemplate.from_messages([
    ("human", "{question}"),
    ("ai", "{answer}"),
])
examples = [
    {"question": "Please calculate: what is 2+2?", "answer": "4"},
    {"question": "Please calculate: what is 2+3?", "answer": "5"},
    {"question": "Please calculate: what is 20*15?", "answer": "300"},
]

# 2. Create the few-shot chat message prompt template
few_shot_prompt = FewShotChatMessagePromptTemplate(
    example_prompt=example_prompt,
    examples=examples,
)
print("Few-shot example template:", few_shot_prompt.format())

# 3. Build the final prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a chatbot capable of solving complex math problems."),
    few_shot_prompt,
    ("human", "{question}"),
])

# 4. Initialize the language model and chain
llm = ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0)
chain = prompt | llm | StrOutputParser()

# 5. Invoke the chain to get results
print(chain.invoke("Please calculate: what is 14*15?"))

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 2.response_fallback_retriever.py
"""
import os
from typing import List

import dotenv
import weaviate
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_weaviate import WeaviateVectorStore
from weaviate.auth import AuthApiKey

dotenv.load_dotenv()


class StepBackRetriever(BaseRetriever):
    """A retriever that rewrites queries to more general or preparatory questions before retrieving."""
    retriever: BaseRetriever
    llm: BaseLanguageModel

    def _get_relevant_documents(
            self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """Rewrites the input query to a fallback question and then retrieves documents."""
        # 1. Prepare few-shot examples for the fallback rewriting
        examples = [
            {"input": "Are there any courses on AI application development on the platform?",
             "output": "What courses does the platform offer?"},
            {"input": "Which country was Ling born in?", "output": "What is ling's background?"},
            {"input": "Can a driver drive at high speed?", "output": "What can a driver do?"},
        ]
        example_prompt = ChatPromptTemplate.from_messages([
            ("human", "{input}"),
            ("ai", "{output}"),
        ])
        few_shot_prompt = FewShotChatMessagePromptTemplate(
            examples=examples,
            example_prompt=example_prompt,
        )

        # 2. Build the prompt for generating the fallback question
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are an expert in world knowledge. Your task is to rewrite questions into more general or preliminary questions to make them easier to answer, using the examples as guidance."),
            few_shot_prompt,
            ("human", "{question}"),
        ])

        # 3. Create the chain: rewrite the question and retrieve documents
        chain = (
                {"question": RunnablePassthrough()}
                | prompt
                | self.llm
                | StrOutputParser()
                | self.retriever
        )

        return chain.invoke(query)


# 1. Initialize the vector database and retriever
db = WeaviateVectorStore(
    client=weaviate.connect_to_wcs(
        cluster_url=os.environ.get("WC_CLUSTER_URL"),
        auth_credentials=AuthApiKey(os.environ["WCD_API_KEY"]),
    ),
    index_name="DatasetDemo",
    text_key="text",
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)
retriever = db.as_retriever(search_type="mmr")

# 2. Create the StepBackRetriever
step_back_retriever = StepBackRetriever(
    retriever=retriever,
    llm=ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0),
)

# 3. Retrieve documents using a fallback query
documents = step_back_retriever.invoke(
    "Will artificial intelligence bring about earth-shattering changes to the world?")
print(documents)
print(len(documents))
