from typing import Any

import dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Load environment variables
dotenv.load_dotenv()

# Define the prompt template
prompt = ChatPromptTemplate.from_template("{query}")

# Define the LLM model
llm = ChatOpenAI(model="gpt-3.5-turbo-16k")

# Define the output parser
parser = StrOutputParser()
list = [prompt, llm, parser]


# Define a class for chaining components
class Chain:
    def __init__(self, steps: list):
        self.steps = steps

    def invoke(self, input: Any) -> Any:
        output = input
        for step in self.steps:
            output = step.invoke(output)
            print(step)
            print("Execution Result:")
            print(output)
            print("===============")
        return output


# # Create a chain with prompt, LLM, and parser
# chain = Chain([prompt, llm, parser])
#
# # Execute the chain with an example input
# print(chain.invoke({"query": "Hello, how are you?"}))

chain = prompt | llm | parser
print(chain.invoke({"query": "Hello, how are you?"}))
