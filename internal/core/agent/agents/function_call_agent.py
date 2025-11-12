#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : function_call_agent.py
"""
import json
import time
import uuid
from threading import Thread
from typing import Literal, Generator

from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    RemoveMessage,
)
from langchain_core.messages import messages_to_dict
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from internal.core.agent.entities.agent_entity import AgentState, AGENT_SYSTEM_PROMPT_TEMPLATE
from internal.core.agent.entities.queue_entity import AgentQueueEvent, QueueEvent
from internal.exception import FailException
from .base_agent import BaseAgent


class FunctionCallAgent(BaseAgent):
    """Agent implementation based on function/tool invocation."""

    def run(
            self,
            query: str,
            history: list[AnyMessage] = None,
            long_term_memory: str = "",
    ) -> Generator[AgentQueueEvent, None, None]:
        """Execute the agent workflow and stream results using yield."""
        # 1. Preprocess input data
        if history is None:
            history = []

        # 2. Build the LangGraph agent
        agent = self._build_graph()

        # 3. Run the agent in a separate thread
        thread = Thread(
            target=agent.invoke,
            args=(
                {
                    "messages": [HumanMessage(content=query)],
                    "history": history,
                    "long_term_memory": long_term_memory,
                },
            ),
        )
        thread.start()

        # 4. Use the queue manager to listen and stream responses
        yield from self.agent_queue_manager.listen()

    def _build_graph(self) -> CompiledStateGraph:
        """Build and compile the LangGraph agent graph."""
        # 1. Create a new graph
        graph = StateGraph(AgentState)

        # 2. Add nodes
        graph.add_node("long_term_memory_recall", self._long_term_memory_recall_node)
        graph.add_node("llm", self._llm_node)
        graph.add_node("tools", self._tools_node)

        # 3. Define edges and set entry and exit points
        graph.set_entry_point("long_term_memory_recall")
        graph.add_edge("long_term_memory_recall", "llm")
        graph.add_conditional_edges("llm", self._tools_condition)
        graph.add_edge("tools", "llm")

        # 4. Compile and return the graph
        agent = graph.compile()
        return agent

    def _long_term_memory_recall_node(self, state: AgentState) -> AgentState:
        """Node for recalling long-term memory."""
        # 1. Check if long-term memory recall is enabled
        long_term_memory = ""
        if self.agent_config.enable_long_term_memory:
            long_term_memory = state["long_term_memory"]
            self.agent_queue_manager.publish(
                AgentQueueEvent(
                    id=uuid.uuid4(),
                    task_id=self.agent_queue_manager.task_id,
                    event=QueueEvent.LONG_TERM_MEMORY_RECALL,
                    observation=long_term_memory,
                )
            )

        # 2. Construct initial system messages with preset prompt and recalled memory
        preset_messages = [
            SystemMessage(
                AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                    preset_prompt=self.agent_config.preset_prompt,
                    long_term_memory=long_term_memory,
                )
            )
        ]

        # 3. Append short-term history messages, if available
        history = state["history"]
        if isinstance(history, list) and len(history) > 0:
            # 4. Validate message alternation pattern [Human, AI, Human, AI, ...]
            if len(history) % 2 != 0:
                raise FailException("Invalid message format in agent history.")
            preset_messages.extend(history)

        # 5. Add the current user query
        human_message = state["messages"][-1]
        preset_messages.append(HumanMessage(human_message.content))

        # 6. Replace the original user message with the combined preset messages
        return {"messages": [RemoveMessage(id=human_message.id), *preset_messages], }

    def _llm_node(self, state: AgentState) -> AgentState:
        """Node for interacting with the large language model (LLM)."""
        # 1. Retrieve model and initialize identifiers
        id = uuid.uuid4()
        start_at = time.perf_counter()
        llm = self.agent_config.llm

        # 2. Bind tools to the model if applicable
        if hasattr(llm, "bind_tools") and callable(getattr(llm, "bind_tools")) and len(self.agent_config.tools) > 0:
            llm = llm.bind_tools(self.agent_config.tools)

        # 3. Stream model output
        gathered = None
        is_first_chunk = True
        generation_type = ""
        for chunk in llm.stream(state["messages"]):
            if is_first_chunk:
                gathered = chunk
                is_first_chunk = False
            else:
                gathered += chunk

            # 4. Determine generation type: reasoning or message
            if not generation_type:
                if chunk.tool_calls:
                    generation_type = "thought"
                elif chunk.content:
                    generation_type = "message"

            # 5. If message generation, publish an agent message event
            if generation_type == "message":
                self.agent_queue_manager.publish(
                    AgentQueueEvent(
                        id=id,
                        task_id=self.agent_queue_manager.task_id,
                        event=QueueEvent.AGENT_MESSAGE,
                        thought=chunk.content,
                        messages=messages_to_dict(state["messages"]),
                        answer=chunk.content,
                        latency=(time.perf_counter() - start_at),
                    )
                )

            # 6.If type is reasoning
            if generation_type == "thought":
                self.agent_queue_manager.publish(AgentQueueEvent(
                    id=id,
                    task_id=self.agent_queue_manager.task_id,
                    event=QueueEvent.AGENT_THOUGHT,
                    messages=messages_to_dict(state["messages"]),
                    latency=(time.perf_counter() - start_at),
                ))
            elif generation_type == "message":
                # 7. If a final answer was generated, stop listening
                self.agent_queue_manager.stop_listen()

        return {"messages": [gathered]}

    def _tools_node(self, state: AgentState) -> AgentState:
        """Node for executing tools or external functions."""
        # 1. Convert the tool list to a name-indexed dictionary
        tools_by_name = {tool.name: tool for tool in self.agent_config.tools}

        # 2. Extract tool call parameters from the last message
        tool_calls = state["messages"][-1].tool_calls

        # 3. Execute each tool call and assemble tool messages
        messages = []
        for tool_call in tool_calls:
            id = uuid.uuid4()
            start_at = time.perf_counter()

            # 4. Retrieve and invoke the tool
            tool = tools_by_name[tool_call["name"]]
            tool_result = tool.invoke(tool_call["args"])

            # 5. Append tool execution result as a message
            messages.append(
                ToolMessage(
                    tool_call_id=tool_call["id"],
                    content=json.dumps(tool_result),
                    name=tool_call["name"],
                )
            )

            # 6. Determine the event type and publish it
            event = (
                QueueEvent.AGENT_ACTION
                if tool_call["name"] != "dataset_retrieval"
                else QueueEvent.DATASET_RETRIEVAL
            )
            self.agent_queue_manager.publish(
                AgentQueueEvent(
                    id=id,
                    task_id=self.agent_queue_manager.task_id,
                    event=event,
                    observation=json.dumps(tool_result),
                    tool=tool_call["name"],
                    tool_input=tool_call["args"],
                    latency=(time.perf_counter() - start_at),
                )
            )

        return {"messages": messages}

    @classmethod
    def _tools_condition(cls, state: AgentState) -> Literal["tools", "__end__"]:
        """Determine whether to execute the tools node or end the workflow."""
        # 1. Get the last AI-generated message
        messages = state["messages"]
        ai_message = messages[-1]

        # 2. Check if tool calls exist; if so, run tools, otherwise end
        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"

        return END
