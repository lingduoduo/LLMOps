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
from internal.core.agent.entities.queue_entity import AgentResult, AgentThought, QueueEvent
from internal.exception import FailException
from .agent_queue_manager import AgentQueueManager


class BaseAgent(Serializable, Runnable):
    """Base agent class built on top of Runnable."""
    llm: BaseLanguageModel
    agent_config: AgentConfig
    _agent: CompiledStateGraph = PrivateAttr(None)
    _agent_queue_manager: AgentQueueManager = PrivateAttr(None)

    class Config:
        # Allow arbitrary types without validation
        arbitrary_types_allowed = True

    def __init__(
            self,
            llm: BaseLanguageModel,
            agent_config: AgentConfig,
            *args,
            **kwargs,
    ):
        """Constructor: initialize agent graph structure."""
        super().__init__(*args, llm=llm, agent_config=agent_config, **kwargs)
        self._agent = self._build_agent()
        self._agent_queue_manager = AgentQueueManager(
            user_id=agent_config.user_id,
            invoke_from=agent_config.invoke_from,
        )

    @abstractmethod
    def _build_agent(self) -> CompiledStateGraph:
        """Build the agent graph — must be implemented by subclass."""
        raise NotImplementedError("_build_agent() not implemented")

    def invoke(self, input: AgentState, config: Optional[RunnableConfig] = None) -> AgentResult:
        """Blocking invocation: returns the complete output after processing."""
        # 1. Call stream() to get event outputs
        agent_result = AgentResult(query=input["messages"][0].content)
        agent_thoughts = {}

        for agent_thought in self.stream(input, config):
            # 2. Convert event id to string
            event_id = str(agent_thought.id)

            # 3. Record all events except ping
            if agent_thought.event != QueueEvent.PING:

                # 4. Special handling for agent_message; this event type accumulates output
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:

                    # 5. If this event id has not been seen, initialize it
                    if event_id not in agent_thoughts:
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 7. Accumulate thought and answer content
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(update={
                            "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                            "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                            "latency": agent_thought.latency,
                        })

                    # 8. Append answer text to final result
                    agent_result.answer += agent_thought.answer

                else:
                    # 9. Other event types override previous values
                    agent_thoughts[event_id] = agent_thought

                    # 10. If event is STOP/TIMEOUT/ERROR, update status and error
                    if agent_thought.event in [QueueEvent.STOP, QueueEvent.TIMEOUT, QueueEvent.ERROR]:
                        agent_result.status = agent_thought.event
                        agent_result.error = (
                            agent_thought.observation if agent_thought.event == QueueEvent.ERROR else ""
                        )

        # 11. Convert thought dictionary to list
        agent_result.agent_thoughts = [agent_thought for agent_thought in agent_thoughts.values()]

        # 12. Fill in message used to generate the final answer
        agent_result.message = next(
            (agent_thought.message for agent_thought in agent_thoughts.values()
             if agent_thought.event == QueueEvent.AGENT_MESSAGE),
            []
        )

        # 13. Calculate total latency
        agent_result.latency = sum(
            agent_thought.latency for agent_thought in agent_thoughts.values()
        )

        return agent_result

    def stream(
            self,
            input: AgentState,
            config: Optional[RunnableConfig] = None,
            **kwargs: Optional[Any],
    ) -> Iterator[AgentThought]:
        """Stream output: returns an event whenever a node or LLM generates a token."""
        # 1. Ensure agent graph is built
        if not self._agent:
            raise FailException("Agent graph was not successfully built, please verify and retry.")

        # 2. Initialize task id and input metadata
        input["task_id"] = input.get("task_id", uuid.uuid4())
        input["history"] = input.get("history", [])
        input["iteration_count"] = input.get("iteration_count", 0)

        # 3. Start agent computation in a background thread
        thread = Thread(
            target=self._agent.invoke,
            args=(input,)
        )
        thread.start()

        # 4. Use queue manager to listen and yield streaming events
        yield from self._agent_queue_manager.listen(input["task_id"])

    @property
    def agent_queue_manager(self) -> AgentQueueManager:
        """Read-only property: return the agent queue manager."""
        return self._agent_queue_manager
