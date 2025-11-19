#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : agent_entity.py
"""
from uuid import UUID

from langchain_core.messages import AnyMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool
from langgraph.graph import MessagesState

from internal.entity.app_entity import DEFAULT_APP_CONFIG
from internal.entity.conversation_entity import InvokeFrom

# Agent system preset prompt template
AGENT_SYSTEM_PROMPT_TEMPLATE = """You are a highly customized agent application designed to provide users with accurate, professional content generation and question answering. Please strictly follow the rules below:

1. **Preset task execution**
  - You must use the user-provided preset prompt (PRESET-PROMPT) to generate the required content, ensuring that your output aligns with the user’s expectations and instructions.

2. **Tool usage and parameter generation**
  - When needed, you may call bound external tools (such as knowledge base retrieval, computation tools, etc.) and generate appropriate call parameters that meet task requirements, ensuring accurate and efficient tool usage.

3. **Conversation history and long-term memory**
  - You may reference `conversation history` together with summarized `long-term memory` to provide more personalized and context-aware responses. This helps maintain consistency across multi-turn interactions and deliver more precise feedback.

4. **External knowledge base retrieval**
  - If the user’s question goes beyond your current knowledge scope or requires additional information, you may call `recall_dataset` (knowledge base retrieval tool) to obtain external knowledge so that your answer is complete and correct.

5. **Efficiency and conciseness**
  - Maintain a precise understanding of user needs and respond efficiently. Provide concise and effective answers, and avoid overly long or irrelevant content.

<preset_prompt>
{preset_prompt}
</preset_prompt>

<long_term_memory>
{long_term_memory}
</long_term_memory>
"""


class AgentConfig(BaseModel):
    """
    Agent configuration information, including:
    LLM model, preset prompt, associated tools/plugins, knowledge bases,
    workflows, whether long-term memory is enabled, etc.
    Can be extended later as needed.
    """
    # Unique user identifier and invocation source; default source is WEB_APP
    user_id: UUID
    invoke_from: InvokeFrom = InvokeFrom.WEB_APP

    # Maximum number of iterations
    max_iteration_count: int = 5

    # Agent preset system prompt
    system_prompt: str = AGENT_SYSTEM_PROMPT_TEMPLATE
    # Preset prompt, default is empty; this value is set by the frontend user
    # during configuration and is injected into system_prompt
    preset_prompt: str = ""

    # Whether long-term memory is enabled for the agent
    # (conversation summarization / long-term memory)
    enable_long_term_memory: bool = False

    # List of tools used by the agent
    tools: list[BaseTool] = Field(default_factory=list)

    # Review / moderation configuration
    review_config: dict = Field(default_factory=lambda: DEFAULT_APP_CONFIG["review_config"])


class AgentState(MessagesState):
    """Agent state class"""
    task_id: UUID  # Task ID corresponding to this run; each execution uses a separate task ID
    iteration_count: int  # Iteration count, default is 0
    history: list[AnyMessage]  # Short-term memory (conversation history)
    long_term_memory: str  # Long-term memory


# Knowledge base retrieval tool name
DATASET_RETRIEVAL_TOOL_NAME = "dataset_retrieval"

# Response shown when the agent exceeds the maximum number of iterations
MAX_ITERATION_RESPONSE = "The current agent has exceeded the maximum allowed number of iterations. Please try again."
