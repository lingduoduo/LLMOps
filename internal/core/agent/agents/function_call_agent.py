#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : function_call_agent.py
"""
import json
import logging
import re
import time
import uuid
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, RemoveMessage, AIMessage
from langchain_core.messages import messages_to_dict
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from internal.core.agent.entities.agent_entity import (
    AgentState,
    AGENT_SYSTEM_PROMPT_TEMPLATE,
    DATASET_RETRIEVAL_TOOL_NAME,
    MAX_ITERATION_RESPONSE,
)
from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.exception import FailException
from .base_agent import BaseAgent
from ...language_model.entities.model_entity import ModelFeature


class FunctionCallAgent(BaseAgent):
    """Agent that supports function/tool calls."""

    def _build_agent(self) -> CompiledStateGraph:
        """Build the LangGraph state graph."""
        # 1. Create graph
        graph = StateGraph(AgentState)

        # 2. Add nodes
        graph.add_node("preset_operation", self._preset_operation_node)
        graph.add_node("long_term_memory_recall", self._long_term_memory_recall_node)
        graph.add_node("llm", self._llm_node)
        graph.add_node("tools", self._tools_node)

        # 3. Add edges and set entry/exit
        graph.set_entry_point("preset_operation")
        graph.add_conditional_edges("preset_operation", self._preset_operation_condition)
        graph.add_edge("long_term_memory_recall", "llm")
        graph.add_conditional_edges("llm", self._tools_condition)
        graph.add_edge("tools", "llm")

        # 4. Compile and return the agent graph
        agent = graph.compile()

        return agent

    def _preset_operation_node(self, state: AgentState) -> AgentState:
        """Preset operations such as input auditing, preprocessing, and conditional routing."""
        # 1. Get review config and user query
        review_config = self.agent_config.review_config
        query = state["messages"][-1].content

        # 2. Input auditing
        if review_config["enable"] and review_config["inputs_config"]["enable"]:
            contains_keyword = any(keyword in query for keyword in review_config["keywords"])

            # 3. If query contains sensitive keywords, send preset response
            if contains_keyword:
                preset_response = review_config["inputs_config"]["preset_response"]

                self.agent_queue_manager.publish(
                    state["task_id"],
                    AgentThought(
                        id=uuid.uuid4(),
                        task_id=state["task_id"],
                        event=QueueEvent.AGENT_MESSAGE,
                        thought=preset_response,
                        message=messages_to_dict(state["messages"]),
                        answer=preset_response,
                        latency=0,
                    )
                )
                self.agent_queue_manager.publish(
                    state["task_id"],
                    AgentThought(id=uuid.uuid4(), task_id=state["task_id"], event=QueueEvent.AGENT_END)
                )

                return {"messages": [AIMessage(preset_response)]}

        return {"messages": []}

    def _long_term_memory_recall_node(self, state: AgentState) -> AgentState:
        """Recall long-term memory if enabled, and prepare the prompt."""
        # 1. Determine if long-term memory recall is needed
        long_term_memory = ""
        if self.agent_config.enable_long_term_memory:
            long_term_memory = state["long_term_memory"]

            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.LONG_TERM_MEMORY_RECALL,
                    observation=long_term_memory,
                )
            )

        # 2. Build preset system message
        preset_messages = [
            SystemMessage(
                AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                    preset_prompt=self.agent_config.preset_prompt,
                    long_term_memory=long_term_memory,
                )
            )
        ]

        # 3. Append short-term conversation history
        history = state["history"]
        if isinstance(history, list) and len(history) > 0:
            # 4. Validate alternating history: [human, ai, human, ai, ...]
            if len(history) % 2 != 0:
                self.agent_queue_manager.publish_error(state["task_id"], "Invalid message history format")
                logging.exception(
                    f"Invalid agent message history, len(history)={len(history)}, history={json.dumps(messages_to_dict(history))}"
                )
                raise FailException("Invalid agent message history")

            # 5. Append history
            preset_messages.extend(history)

        # 6. Append user query
        human_message = state["messages"][-1]
        preset_messages.append(HumanMessage(human_message.content))

        # 7. Replace original user message with preset prompt + history
        return {
            "messages": [RemoveMessage(id=human_message.id), *preset_messages],
        }

    def _llm_node(self, state: AgentState) -> AgentState:
        """LLM node: generate messages or function calls."""
        # 1. Enforce max iteration limit
        if state["iteration_count"] > self.agent_config.max_iteration_count:
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_MESSAGE,
                    thought=MAX_ITERATION_RESPONSE,
                    message=messages_to_dict(state["messages"]),
                    answer=MAX_ITERATION_RESPONSE,
                    latency=0,
                )
            )
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(id=uuid.uuid4(), task_id=state["task_id"], event=QueueEvent.AGENT_END)
            )
            return {"messages": [AIMessage(MAX_ITERATION_RESPONSE)]}

        # 2. Prepare LLM instance
        id = uuid.uuid4()
        start_at = time.perf_counter()
        llm = self.llm

        # 3. Bind tools if the model supports function calls
        if (
                ModelFeature.TOOL_CALL in llm.features
                and hasattr(llm, "bind_tools")
                and callable(llm.bind_tools)
                and len(self.agent_config.tools) > 0
        ):
            llm = llm.bind_tools(self.agent_config.tools)

        # 4. Stream LLM output
        gathered = None
        is_first_chunk = True
        generation_type = ""

        try:
            for chunk in llm.stream(state["messages"]):
                # gather streamed chunks
                if is_first_chunk:
                    gathered = chunk
                    is_first_chunk = False
                else:
                    gathered += chunk

                # determine output type (message vs tool call)
                if not generation_type:
                    if chunk.tool_calls:
                        generation_type = "thought"
                    elif chunk.content:
                        generation_type = "message"

                # If LLM is generating a message, publish incremental output
                if generation_type == "message":
                    review_config = self.agent_config.review_config
                    content = chunk.content

                    # simple output filtering
                    if review_config["enable"] and review_config["outputs_config"]["enable"]:
                        for keyword in review_config["keywords"]:
                            content = re.sub(re.escape(keyword), "**", content, flags=re.IGNORECASE)

                    self.agent_queue_manager.publish(
                        state["task_id"],
                        AgentThought(
                            id=id,
                            task_id=state["task_id"],
                            event=QueueEvent.AGENT_MESSAGE,
                            thought=content,
                            message=messages_to_dict(state["messages"]),
                            answer=content,
                            latency=(time.perf_counter() - start_at),
                        )
                    )

        except Exception as e:
            logging.exception(f"Error in LLM node: {str(e)}")
            self.agent_queue_manager.publish_error(state["task_id"], f"LLM node error: {str(e)}")
            raise e

        # 6. Publish tool-call thoughts
        if generation_type == "thought":
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=id,
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_THOUGHT,
                    thought=json.dumps(gathered.tool_calls),
                    message=messages_to_dict(state["messages"]),
                    latency=(time.perf_counter() - start_at),
                )
            )

        # If final answer is generated without tool calls — end the agent
        elif generation_type == "message":
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(id=uuid.uuid4(), task_id=state["task_id"], event=QueueEvent.AGENT_END)
            )

        return {"messages": [gathered], "iteration_count": state["iteration_count"] + 1}

    def _tools_node(self, state: AgentState) -> AgentState:
        """Tool execution node."""
        # 1. Map tools by name
        tools_by_name = {tool.name: tool for tool in self.agent_config.tools}

        # 2. Extract tool call parameters
        tool_calls = state["messages"][-1].tool_calls

        # 3. Execute tools and build responses
        messages = []
        for tool_call in tool_calls:
            id = uuid.uuid4()
            start_at = time.perf_counter()

            try:
                tool = tools_by_name[tool_call["name"]]
                tool_result = tool.invoke(tool_call["args"])
            except Exception as e:
                tool_result = f"Tool execution error: {str(e)}"

            # create tool message
            messages.append(
                ToolMessage(
                    tool_call_id=tool_call["id"],
                    content=json.dumps(tool_result),
                    name=tool_call["name"],
                )
            )

            # determine event type
            event = (
                QueueEvent.AGENT_ACTION
                if tool_call["name"] != DATASET_RETRIEVAL_TOOL_NAME
                else QueueEvent.DATASET_RETRIEVAL
            )

            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=id,
                    task_id=state["task_id"],
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
        """Determine whether to enter the tools node or end."""
        ai_message = state["messages"][-1]

        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"

        return END

    @classmethod
    def _preset_operation_condition(cls, state: AgentState) -> Literal["long_term_memory_recall", "__end__"]:
        """Determine whether the preset step triggered a response."""
        message = state["messages"][-1]

        # If message is AI type, auditing triggered → end
        if message.type == "ai":
            return END

        return "long_term_memory_recall"
