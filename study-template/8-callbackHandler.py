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
    "你好，你是谁？",  # Example input: "Hello, who are you?"
    config={"callbacks": [StdOutCallbackHandler()]}
)

# Step 5: Process and display the output
for chunk in content:
    print(chunk)

from langchain_core.callbacks import BaseCallbackHandler
from typing import Optional, Union, Any, Dict, List
from uuid import UUID
from langchain_core.schema import GenerationChunk, ChatGenerationChunk


class LLMOpsCallbackHandler(BaseCallbackHandler):
    """Custom callback handler for LLMOps."""

    def on_llm_start(
            self,
            serialized: Dict[str, Any],
            prompts: List[str],
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            tags: Optional[List[str]] = None,
            metadata: Optional[Dict[str, Any]] = None,
            **kwargs: Any
    ) -> Any:
        print("on_llm_start serialized:", serialized)
        print("on_llm_start prompts:", prompts)

    def on_llm_new_token(
            self,
            token: str,
            chunk: Optional[Union[GenerationChunk, ChatGenerationChunk]] = None,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any
    ) -> Any:
        print("New token generated:", token)
