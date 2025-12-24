### LangChain Expression Language (LCEL)
### Case 1
from dotenv import load_dotenv

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel
from langchain_openai import ChatOpenAI

# Load environment variables
load_dotenv()

# 1. Define two prompt templates
joke_prompt = ChatPromptTemplate.from_template(
    "{subject} Please tell a cold joke about {subject}, keep it as short as possible.")
poem_prompt = ChatPromptTemplate.from_template(
    "{subject} Please write a poem about {subject}, keep it as short as possible.")

# 2. Create a large language model
llm = ChatOpenAI(model="gpt-3.5-turbo-16k")

# 3. Create an output parser
parser = StrOutputParser()

# 4. Construct two processing chains
joke_chain = joke_prompt | llm | parser
poem_chain = poem_prompt | llm | parser

# 5. Create a parallel runnable component
map_chain = RunnableParallel(joke=joke_chain, poem=poem_chain)

# 6. Run the parallel component and get the response
resp = map_chain.invoke({"subject": "programmer"})

# Print the response
print(resp)

print("============")

### Case 2
from dotenv import load_dotenv

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Load environment variables
load_dotenv()


# Define a retrieval function (simulated)
def retrieval(query: str) -> str:
    """
    Simulates a retriever: takes a query and returns some text.
    """
    print(f"Executing retrieval for query: {query}")
    return "AI: My name is Ling, and I am an engineer."


# 1. Define the prompt template
prompt = ChatPromptTemplate.from_template(
    """Please answer the user's question based on the provided context.
<context>
{context}
<context>
The user's question is: {query}"""
)

# 2. Create a large language model instance
llm = ChatOpenAI(model="gpt-3.5-turbo")

# 3. Create an output parser
parser = StrOutputParser()

# 4. Define the processing chain
chain = prompt | llm | parser

# content = chain.invoke({"context": "", "query": "hello"})
# print(content)

content = chain.invoke({"context": retrieval("Hello, who am I"), "query": "hello"})
print(content)

print("============")

from dotenv import load_dotenv

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

# Load environment variables
load_dotenv()

# 1. Define the prompt template
prompt = ChatPromptTemplate.from_template("{query}")

# 2. Create the large language model instance
llm = ChatOpenAI(model="gpt-4")

# 3. Create the processing chain
chain = RunnablePassthrough(context=lambda x: retrieval(x["query"])) | prompt | llm | StrOutputParser()

# 4. Invoke the chain and get the result
content = chain.invoke({"query": "Hello, who am I?"})

# Print the response
print(content)
