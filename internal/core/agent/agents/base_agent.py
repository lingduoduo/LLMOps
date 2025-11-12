#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : base_agent.py
"""
from abc import ABC, abstractmethod
from typing import Generator

from langchain_core.messages import AnyMessage

from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import AgentQueueEvent
from .agent_queue_manager import AgentQueueManager


class BaseAgent(ABC):
    """Base class for all agents in the LLMOps project."""
    agent_config: AgentConfig
    agent_queue_manager: AgentQueueManager

    def __init__(
            self,
            agent_config: AgentConfig,
            agent_queue_manager: AgentQueueManager,
    ):
        """Constructor — initialize the agent configuration and queue manager."""
        self.agent_config = agent_config
        self.agent_queue_manager = agent_queue_manager

    @abstractmethod
    def run(
            self,
            query: str,
            history: list[AnyMessage] = None,
            long_term_memory: str = "",
    ) -> Generator[AgentQueueEvent, None, None]:
        """Agent execution function.

        This method should process the provided user query, along with
        short-term and long-term memory, and generate the appropriate
        agent responses.

        Args:
            query (str): The user's original input question.
            history (list[AnyMessage], optional): Short-term memory of previous interactions.
            long_term_memory (str, optional): Stored long-term context or summary.

        Yields:
            AgentQueueEvent: Streamed agent events or outputs during execution.
        """
        raise NotImplementedError("The 'run' method for the agent has not been implemented.")
