#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.LangGraph_CRAG_example.py
"""
import os
from typing import TypedDict, Any

import dotenv
import weaviate
from langchain_community.tools import GoogleSerperRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_weaviate import WeaviateVectorStore
from langgraph.graph import StateGraph
from weaviate.auth import AuthApiKey

dotenv.load_dotenv()


class GradeDocument(BaseModel):
    """Pydantic model for grading document relevance"""
    binary_score: str = Field(description="Is the document relevant to the question? Please answer 'yes' or 'no'.")


class GoogleSerperArgsSchema(BaseModel):
    query: str = Field(description="The query string to execute a Google search")


class GraphState(TypedDict):
    """Graph application state data"""
    question: str  # Original question
    generation: str  # Generated content from LLM
    web_search: str  # Web search status
    documents: list[str]  # List of documents


def format_docs(docs: list[Document]) -> str:
    """Format list of documents into a single string"""
    return "\n\n".join([doc.page_content for doc in docs])


# 1. Initialize LLM
llm = ChatOpenAI(model="gpt-4o-mini")

# 2. Set up retriever
vector_store = WeaviateVectorStore(
    client=weaviate.connect_to_wcs(
        cluster_url=os.environ.get("WC_CLUSTER_URL"),
        auth_credentials=AuthApiKey(os.environ["WCD_API_KEY"]),
    ),
    index_name="LLMOps",
    text_key="text",
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)
retriever = vector_store.as_retriever(search_type="mmr")

# 3. Grader for retrieved documents
system = """You are an evaluator of whether a retrieved document is relevant to the user's question. 
If the document contains keywords or semantics related to the question, grade it as relevant. 
Return 'yes' or 'no'."""
grade_prompt = ChatPromptTemplate.from_messages([
    ("system", system),
    ("human", "Retrieved Document: \n\n{document}\n\nUser Question: {question}"),
])
retrieval_grader = grade_prompt | llm.with_structured_output(GradeDocument)

# 4. RAG chain for generation
template = """You are an assistant for question answering. Use the retrieved context to answer the question. 
If unsure, say you don't know. Keep answers concise.

Question: {question}
Context: {context}
Answer: """
prompt = ChatPromptTemplate.from_template(template)
rag_chain = prompt | llm.bind(temperature=0) | StrOutputParser()

# 5. Question rewriting for web search
rewrite_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a question rewriter to optimize queries for web search. Infer semantic intent when possible."
    ),
    ("human", "Here is the original question:\n\n{question}\n\nPlease propose an improved version."),
])
question_rewriter = rewrite_prompt | llm.bind(temperature=0) | StrOutputParser()

# 6. Define Google search tool
google_serper = GoogleSerperRun(
    name="google_serper",
    description="A low-cost Google search API. Use it for answering current events. The input is a search query.",
    args_schema=GoogleSerperArgsSchema,
    api_wrapper=GoogleSerperAPIWrapper(),
)


# 7. Graph node functions
def retrieve(state: GraphState) -> Any:
    print("--- Retrieval Node ---")
    question = state["question"]
    documents = retriever.invoke(question)
    return {"documents": documents, "question": question}


def generate(state: GraphState) -> Any:
    print("--- LLM Generation Node ---")
    question = state["question"]
    documents = state["documents"]
    generation = rag_chain.invoke({"context": format_docs(documents), "question": question})
    return {"question": question, "documents": documents, "generation": generation}


def grade_documents(state: GraphState) -> Any:
    print("--- Document Relevance Grading Node ---")
    question = state["question"]
    documents = state["documents"]

    filtered_docs = []
    web_search = "no"
    for doc in documents:
        score: GradeDocument = retrieval_grader.invoke({
            "question": question, "document": doc.page_content,
        })
        grade = score.binary_score
        if grade.lower() == "yes":
            print("--- Document is relevant ---")
            filtered_docs.append(doc)
        else:
            print("--- Document is NOT relevant ---")
            web_search = "yes"
    return {**state, "documents": filtered_docs, "web_search": web_search}


def transform_query(state: GraphState) -> Any:
    print("--- Query Rewriting Node ---")
    question = state["question"]
    better_question = question_rewriter.invoke({"question": question})
    return {**state, "question": better_question}


def web_search(state: GraphState) -> Any:
    print("--- Web Search Node ---")
    question = state["question"]
    documents = state["documents"]

    search_content = google_serper.invoke({"query": question})
    documents.append(Document(page_content=search_content))
    return {**state, "documents": documents}


def decide_to_generate(state: GraphState) -> Any:
    print("--- Routing Decision Node ---")
    if state["web_search"].lower() == "yes":
        print("--- Proceed to Web Search ---")
        return "transform_query"
    else:
        print("--- Proceed to LLM Generation ---")
        return "generate"


# 8. Build workflow graph
workflow = StateGraph(GraphState)

# 9. Define nodes
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("generate", generate)
workflow.add_node("transform_query", transform_query)
workflow.add_node("web_search_node", web_search)

# 10. Define edges
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "grade_documents")
workflow.add_conditional_edges("grade_documents", decide_to_generate)
workflow.add_edge("transform_query", "web_search_node")
workflow.add_edge("web_search_node", "generate")
workflow.set_finish_point("generate")

# 11. Compile and run
app = workflow.compile()

print(app.invoke({"question": "Can you introduce what LLMOps is?"}))
