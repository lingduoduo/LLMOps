import dotenv
from langchain_core.callbacks import StdOutCallbackHandler
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

# Load environment variables
dotenv.load_dotenv()

# Step 1: Define the prompt template
prompt = ChatPromptTemplate.from_template("{query}")

# Step 2: Initialize the LLM model
llm = ChatOpenAI(model="gpt-3.5-turbo-16k")

# Step 3: Build the processing chain
chain = (
        {"query": RunnablePassthrough()}  # Pass query as input
        | prompt  # Apply the prompt template
        | llm  # Send query to OpenAI LLM
        | StrOutputParser()  # Parse the output into a string
)

# Step 4: Execute the chain with an example query
content = chain.stream(
    "Hello",  # Example input: "Hello, who are you?"
    config={"callbacks": [StdOutCallbackHandler()]}
)

# Step 5: Process and display the output
for chunk in content:
    print(chunk)
