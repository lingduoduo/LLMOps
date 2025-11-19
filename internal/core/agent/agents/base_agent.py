#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : base_agent.py
"""
import uuid
from abc import abstractmethod
from threading import Thread
from typing import Optional, Any, Iterator

from langchain_core.language_models import BaseLanguageModel
from langchain_core.load import Serializable
from langchain_core.pydantic_v1 import PrivateAttr
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from internal.core.agent.entities.agent_entity import AgentConfig, AgentState
from internal.core.agent.entities.queue_entity import AgentResult, AgentThought
from internal.exception import FailException
from .agent_queue_manager import AgentQueueManager


class BaseAgent(Serializable, Runnable):
    """Base agent class built on Runnable"""
    llm: BaseLanguageModel
    agent_config: AgentConfig
    _agent: CompiledStateGraph = PrivateAttr(None)
    _agent_queue_manager: AgentQueueManager = PrivateAttr(None)

    class Config:
        # Allow arbitrary field types without validators
        arbitrary_types_allowed = True

    def __init__(
            self,
            llm: BaseLanguageModel,
            agent_config: AgentConfig,
            *args,
            **kwargs,
    ):
        """Constructor that initializes the agent graph program"""
        super().__init__(*args, llm=llm, agent_config=agent_config, **kwargs)
        self._agent = self._build_agent()
        self._agent_queue_manager = AgentQueueManager(
            user_id=agent_config.user_id,
            invoke_from=agent_config.invoke_from,
        )

    @abstractmethod
    def _build_agent(self) -> CompiledStateGraph:
        """Build the agent graph; must be implemented by subclasses"""
        raise NotImplementedError("_build_agent() is not implemented")

    def invoke(self, input: AgentState, config: Optional[RunnableConfig] = None) -> AgentResult:
        """Block-style response: generate the full content once and return"""
        pass

    def stream(
            self,
            input: AgentState,
            config: Optional[RunnableConfig] = None,
            **kwargs: Optional[Any],
    ) -> Iterator[AgentThought]:
        """
        Streaming output: returns content whenever a node finishes
        or whenever the LLM generates tokens.
        """
        # 1. Check if the subclass has successfully built the agent; if not, raise an error
        if not self._agent:
            raise FailException("Agent has not been successfully built, please verify and try again.")

        # 2. Build the task_id and initialize data
        input["task_id"] = input.get("task_id", uuid.uuid4())
        input["history"] = input.get("history", [])
        input["iteration_count"] = input.get("iteration_count", 0)

        # 3. Create a worker thread and run the agent
        thread = Thread(
            target=self._agent.invoke,
            args=(input,)
        )
        thread.start()

        # 4. Use the queue manager to listen for data and yield an iterator
        yield from self._agent_queue_manager.listen(input["task_id"])

    @property
    def agent_queue_manager(self) -> AgentQueueManager:
        """Read-only property that returns the agent queue manager"""
        return self._agent_queue_manager
