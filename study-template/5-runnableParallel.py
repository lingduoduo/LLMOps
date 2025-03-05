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
