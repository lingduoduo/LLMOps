#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : agent_entity.py
"""
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import AnyMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool
from langgraph.graph import MessagesState

# Agent system preset prompt template
AGENT_SYSTEM_PROMPT_TEMPLATE = """You are a highly customized intelligent agent application designed to provide users with accurate and professional content generation and question answering. Please strictly follow the rules below:

1. **Preset Task Execution**
   - You must generate specific content based on the user-provided preset prompt (PRESET-PROMPT), ensuring that the output meets the user’s expectations and instructions.

2. **Tool Invocation and Parameter Generation**
   - When required by the task, you can call bound external tools (e.g., knowledge base retrieval, computation tools, etc.) and generate parameters that fit the task needs, ensuring the accuracy and efficiency of tool usage.

3. **Conversation History and Long-Term Memory**
   - You can refer to the `conversation history` and combine it with summarized `long-term memory` to provide more personalized and contextually relevant responses. This helps maintain consistency and improve precision across multi-turn conversations.

4. **External Knowledge Base Retrieval**
   - If the user's question exceeds your current knowledge scope or requires additional information, you may invoke the `recall_dataset` (knowledge base retrieval tool) to obtain external data, ensuring your answer is complete and accurate.

5. **Efficiency and Conciseness**
   - Maintain a precise understanding of the user’s needs and respond efficiently. Provide concise, relevant answers and avoid lengthy or unrelated information.

<Preset Prompt>
{preset_prompt}
</Preset Prompt>

<Long-Term Memory>
{long_term_memory}
</Long-Term Memory>
"""


class AgentConfig(BaseModel):
    """Agent configuration information, including: LLM model, preset prompt, associated tools, knowledge base, workflow, and long-term memory options. Extensible for future use."""
    # The LLM used by the agent
    llm: BaseLanguageModel

    # The system-level prompt template for the agent
    system_prompt: str = AGENT_SYSTEM_PROMPT_TEMPLATE

    # User-provided preset prompt; defaults to empty and filled into the system_prompt at runtime
    preset_prompt: str = ""

    # Whether long-term memory is enabled
    enable_long_term_memory: bool = False

    # List of tools used by the agent
    tools: list[BaseTool] = Field(default_factory=list)


class AgentState(MessagesState):
    """Agent state class"""
    history: list[AnyMessage]
    long_term_memory: str
