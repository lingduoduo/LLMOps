#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.LLMChain_Usage_Techniques.py
"""
import dotenv
from langchain.chains.llm import LLMChain
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Load environment variables
dotenv.load_dotenv()

# Create a prompt template
prompt = ChatPromptTemplate.from_template("Please tell a cold joke about the topic: {subject}")

# Initialize the language model
llm = ChatOpenAI(model="gpt-3.5-turbo-16k")

# Create the LLMChain
chain = LLMChain(prompt=prompt, llm=llm)

# Example outputs
# print(chain("Programmer"))
# print(chain.run("Programmer"))
# print(chain.apply([{"subject": "Programmer"}]))
# print(chain.generate([{"subject": "Programmer"}]))
# print(chain.predict(subject="Programmer"))

# Invoke the chain with the subject "Programmer"
print(chain.invoke({"subject": "Programmer"}))

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 2.LCEL_Document_Filling_Chain.py
"""
import dotenv
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Load environment variables
dotenv.load_dotenv()

# 1. Create a prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a powerful chatbot that can respond to user questions based on the provided context.\n\n<context>{context}</context>"),
    ("human", "{query}")
])

# 2. Initialize the large language model
llm = ChatOpenAI(model="gpt-4-turbo")

# 3. Create the document chain application
chain = create_stuff_documents_chain(prompt=prompt, llm=llm)

# 4. Document list
documents = [
    Document(page_content="Ling likes green but doesn't like yellow."),
    Document(page_content="Ling likes pink and also somewhat likes red."),
    Document(page_content="Ling likes blue but prefers cyan."),
]

# 5. Invoke the chain
content = chain.invoke({"query": "Please summarize what colors everyone likes.", "context": documents})

print(content)

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 3.Conversation_Chain.py
"""
import dotenv
from langchain.chains.conversation.base import ConversationChain
from langchain_openai import ChatOpenAI

# Load environment variables
dotenv.load_dotenv()

# Initialize the language model
llm = ChatOpenAI(model="gpt-3.5-turbo-16k")

# Create the conversation chain
chain = ConversationChain(llm=llm)

# 1. Start the conversation
content = chain.invoke(
    {"input": "Hello, I'm Ling. I like music and movie. What do you like?"})

print(content)

# 2. Ask a follow-up question using context
content = chain.invoke({"input": "Based on the previous conversation, can you summarize what I like?"})

print(content)
