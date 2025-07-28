import json
import warnings
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import dotenv
from langchain_core.callbacks import StdOutCallbackHandler
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages.base import BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.outputs import GenerationChunk, ChatGenerationChunk
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

warnings.filterwarnings("ignore")


# --- Custom Callback Handler ---
class LLMOpsCallbackHandler(BaseCallbackHandler):
    """自定义LLMOps回调处理器"""

    def on_chat_model_start(
            self,
            serialized: Dict[str, Any],
            messages: List[List[BaseMessage]],
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            tags: Optional[List[str]] = None,
            metadata: Optional[Dict[str, Any]] = None,
            **kwargs: Any,
    ) -> Any:
        print("LLM Model started")
        print("serialized:", json.dumps(serialized, indent=3))
        print("messages:", messages)

    def on_llm_new_token(
            self,
            token: str,
            *,
            chunk: Optional[Union[GenerationChunk, ChatGenerationChunk]] = None,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
    ) -> Any:
        print("LLM New Token started")
        print("token:", token)


class SafeStdOutCallbackHandler(StdOutCallbackHandler):
    def on_chain_start(self, serialized, inputs, **kwargs):
        metadata = kwargs.get("metadata") or {}
        name = metadata.get("name", "UnnamedChain")
        print(f"\n> Entering chain: {name}")


# --- Load env ---
dotenv.load_dotenv()

# --- Define the prompt ---
prompt = ChatPromptTemplate.from_template("{query}")

# --- Create LLM ---
llm = ChatOpenAI(model="gpt-3.5-turbo-16k")

# --- Build the chain ---
chain = (
        {"query": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
)

# --- Run the chain with custom handler ---
output = chain.invoke(
    "hello",
    config={"callbacks": [SafeStdOutCallbackHandler(), LLMOpsCallbackHandler()]}
)
print(output)

resp = chain.stream(
    "hello",
    config={"callbacks": [SafeStdOutCallbackHandler(), LLMOpsCallbackHandler()]}
)
for chunk in resp:
    print(chunk)
