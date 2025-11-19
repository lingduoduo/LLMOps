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


class FunctionCallAgent(BaseAgent):
    """Agent based on function/tool calls"""

    def _build_agent(self) -> CompiledStateGraph:
        """Build and compile the LangGraph graph structure"""
        # 1. Create graph
        graph = StateGraph(AgentState)

        # 2. Add nodes
        graph.add_node("preset_operation", self._preset_operation_node)
        graph.add_node("long_term_memory_recall", self._long_term_memory_recall_node)
        graph.add_node("llm", self._llm_node)
        graph.add_node("tools", self._tools_node)

        # 3. Add edges and set entry/exit points
        graph.set_entry_point("preset_operation")
        graph.add_conditional_edges("preset_operation", self._preset_operation_condition)
        graph.add_edge("long_term_memory_recall", "llm")
        graph.add_conditional_edges("llm", self._tools_condition)
        graph.add_edge("tools", "llm")

        # 4. Compile graph and return
        agent = graph.compile()

        return agent

    def _preset_operation_node(self, state: AgentState) -> AgentState:
        """Preset operations, including: input review, data preprocessing, conditional edges, etc."""
        # 1. Get review config and user query
        review_config = self.agent_config.review_config
        query = state["messages"][-1].content

        # 2. Check whether input review is enabled
        if review_config["enable"] and review_config["inputs_config"]["enable"]:
            contains_keyword = any(keyword in query for keyword in review_config["keywords"])
            # 3. If sensitive keywords are detected, execute the preset response flow
            if contains_keyword:
                preset_response = review_config["inputs_config"]["preset_response"]
                self.agent_queue_manager.publish(state["task_id"], AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_MESSAGE,
                    thought=preset_response,
                    message=messages_to_dict(state["messages"]),
                    answer=preset_response,
                    latency=0,
                ))
                self.agent_queue_manager.publish(state["task_id"], AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_END,
                ))
                return {"messages": [AIMessage(preset_response)]}

        return {"messages": []}

    def _long_term_memory_recall_node(self, state: AgentState) -> AgentState:
        """Long-term memory recall node"""
        # 1. Decide whether long-term memory needs to be recalled based on agent config
        long_term_memory = ""
        if self.agent_config.enable_long_term_memory:
            long_term_memory = state["long_term_memory"]
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.LONG_TERM_MEMORY_RECALL,
                observation=long_term_memory,
            ))

        # 2. Build the preset message list and fill preset_prompt + long_term_memory into the system message
        preset_messages = [
            SystemMessage(AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                preset_prompt=self.agent_config.preset_prompt,
                long_term_memory=long_term_memory,
            ))
        ]

        # 3. Append short-term history messages
        history = state["history"]
        if isinstance(history, list) and len(history) > 0:
            # 4. Validate that history is in alternating form:
            # [human, ai, human, ai, ...]
            if len(history) % 2 != 0:
                self.agent_queue_manager.publish_error(state["task_id"], "Agent history message list format error")
                logging.exception(
                    f"Agent history message list format error, len(history)={len(history)}, "
                    f"history={json.dumps(messages_to_dict(history))}"
                )
                raise FailException("Agent history message list format error")
            # 5. Append history messages
            preset_messages.extend(history)

        # 6. Append the current user message
        human_message = state["messages"][-1]
        preset_messages.append(HumanMessage(human_message.content))

        # 7. Replace the original user message with the new preset message list
        return {
            "messages": [RemoveMessage(id=human_message.id), *preset_messages],
        }

    def _llm_node(self, state: AgentState) -> AgentState:
        """LLM node"""
        # 1. Check whether the current iteration count exceeds the limit
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
                ))
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_END,
                ))
            return {"messages": [AIMessage(MAX_ITERATION_RESPONSE)]}

        # 2. Get the LLM instance from the agent config
        id = uuid.uuid4()
        start_at = time.perf_counter()
        llm = self.llm

        # 3. If the LLM instance has bind_tools and tools are configured, bind tools
        if hasattr(llm, "bind_tools") and callable(getattr(llm, "bind_tools")) and len(self.agent_config.tools) > 0:
            llm = llm.bind_tools(self.agent_config.tools)

        # 4. Stream from the LLM and collect output
        gathered = None
        is_first_chunk = True
        generation_type = ""
        try:
            for chunk in llm.stream(state["messages"]):
                if is_first_chunk:
                    gathered = chunk
                    is_first_chunk = False
                else:
                    gathered += chunk

                # 5. Detect whether the generation is tool-calls or normal text
                if not generation_type:
                    if chunk.tool_calls:
                        generation_type = "thought"
                    elif chunk.content:
                        generation_type = "message"

                # 6. If the generation is a message, publish an agent message event
                if generation_type == "message":
                    # 7. Extract the content and, if enabled, apply output review/masking
                    review_config = self.agent_config.review_config
                    content = chunk.content
                    if review_config["enable"] and review_config["outputs_config"]["enable"]:
                        for keyword in review_config["keywords"]:
                            content = re.sub(re.escape(keyword), "**", content, flags=re.IGNORECASE)

                    self.agent_queue_manager.publish(state["task_id"], AgentThought(
                        id=id,
                        task_id=state["task_id"],
                        event=QueueEvent.AGENT_MESSAGE,
                        thought=content,
                        message=messages_to_dict(state["messages"]),
                        answer=content,
                        latency=(time.perf_counter() - start_at),
                    ))
        except Exception as e:
            logging.exception(f"Error occurred in LLM node, error: {str(e)}")
            self.agent_queue_manager.publish_error(state["task_id"], f"Error occurred in LLM node, error: {str(e)}")
            raise e

        # 6. If the type is "thought", publish an agent reasoning event
        if generation_type == "thought":
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=id,
                task_id=state["task_id"],
                event=QueueEvent.AGENT_THOUGHT,
                thought=json.dumps(gathered.tool_calls),
                message=messages_to_dict(state["messages"]),
                latency=(time.perf_counter() - start_at),
            ))
        elif generation_type == "message":
            # 7. If the LLM directly generated an answer, we have the final response and can end
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.AGENT_END,
            ))

        return {"messages": [gathered], "iteration_count": state["iteration_count"] + 1}

    def _tools_node(self, state: AgentState) -> AgentState:
        """Tool execution node"""
        # 1. Convert the tool list to a name->tool mapping for easy lookup
        tools_by_name = {tool.name: tool for tool in self.agent_config.tools}

        # 2. Extract tool-call parameters from the last message
        tool_calls = state["messages"][-1].tool_calls

        # 3. Execute each tool call and assemble ToolMessages
        messages = []
        for tool_call in tool_calls:
            # 4. Create an ID for this agent action event and record start time
            id = uuid.uuid4()
            start_at = time.perf_counter()

            try:
                # 5. Get the tool and invoke it
                tool = tools_by_name[tool_call["name"]]
                tool_result = tool.invoke(tool_call["args"])
            except Exception as e:
                # 6. If an error occurs, record the error as the tool result
                tool_result = f"Tool execution error: {str(e)}"

            # 7. Add the ToolMessage to the message list
            messages.append(ToolMessage(
                tool_call_id=tool_call["id"],
                content=json.dumps(tool_result),
                name=tool_call["name"],
            ))

            # 7. Determine the event type based on the tool name:
            # agent action vs. dataset retrieval
            event = (
                QueueEvent.AGENT_ACTION
                if tool_call["name"] != DATASET_RETRIEVAL_TOOL_NAME
                else QueueEvent.DATASET_RETRIEVAL
            )
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=id,
                task_id=state["task_id"],
                event=event,
                observation=json.dumps(tool_result),
                tool=tool_call["name"],
                tool_input=tool_call["args"],
                latency=(time.perf_counter() - start_at),
            ))

        return {"messages": messages}

    @classmethod
    def _tools_condition(cls, state: AgentState) -> Literal["tools", "__end__"]:
        """Determine whether the next node should be 'tools' or end."""
        # 1. Extract the last message (AI message) from the state
        messages = state["messages"]
        ai_message = messages[-1]

        # 2. If tool_calls exists and is non-empty, go to tools node; otherwise end
        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"

        return END

    @classmethod
    def _preset_operation_condition(cls, state: AgentState) -> Literal["long_term_memory_recall", "__end__"]:
        """Preset operation conditional edge, used to determine whether to trigger preset response logic."""
        # 1. Get the last message from the state
        message = state["messages"][-1]

        # 2. If the message type is AI, it means the review mechanism already triggered; end directly
        if message.type == "ai":
            return END

        return "long_term_memory_recall"
