#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : react_agent.py
"""
import json
import logging
import re
import time
import uuid

from langchain_core.messages import SystemMessage, messages_to_dict, HumanMessage, RemoveMessage, AIMessage
from langchain_core.tools import render_text_description_and_args

from internal.core.agent.entities.agent_entity import (
    AgentState,
    AGENT_SYSTEM_PROMPT_TEMPLATE,
    REACT_AGENT_SYSTEM_PROMPT_TEMPLATE, MAX_ITERATION_RESPONSE,
)
from internal.core.agent.entities.queue_entity import QueueEvent, AgentThought
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.exception import FailException
from .function_call_agent import FunctionCallAgent


class ReACTAgent(FunctionCallAgent):
    """
    ReACT-based reasoning agent.

    Inherits from FunctionCallAgent and overrides the long_term_memory_node and
    llm_node to implement ReACT-style reasoning when the LLM does not support native tool calls.
    """

    def _long_term_memory_recall_node(self, state: AgentState) -> AgentState:
        """
        Override: long-term memory recall node.

        If the model supports tool calls, delegate to the parent implementation.
        Otherwise, use prompt engineering (with or without tool description) to
        recall long-term memory and construct the final message list.
        """
        # 1. If LLM supports tool_call, directly use the FunctionCallAgent's implementation
        if ModelFeature.TOOL_CALL in self.llm.features:
            return super()._long_term_memory_recall_node(state)

        # 2. Decide whether to recall long-term memory according to agent_config
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
                ),
            )

        # 3. If AGENT_THOUGHT is not supported, use a prompt without tool descriptions
        if ModelFeature.AGENT_THOUGHT not in self.llm.features:
            preset_messages = [
                SystemMessage(
                    AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                        preset_prompt=self.agent_config.preset_prompt,
                        long_term_memory=long_term_memory,
                    )
                )
            ]
        else:
            # 4. If agent reasoning is supported, use REACT_AGENT_SYSTEM_PROMPT_TEMPLATE and include tool descriptions
            preset_messages = [
                SystemMessage(
                    REACT_AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                        preset_prompt=self.agent_config.preset_prompt,
                        long_term_memory=long_term_memory,
                        tool_description=render_text_description_and_args(self.agent_config.tools),
                    )
                )
            ]

        # 5. Append short-term history messages
        history = state["history"]
        if isinstance(history, list) and len(history) > 0:
            # 6. Ensure history is in pairs: [Human, AI, Human, AI, ...]
            if len(history) % 2 != 0:
                error_msg = "Agent history message list format is invalid."
                self.agent_queue_manager.publish_error(state["task_id"], error_msg)
                logging.exception(
                    f"{error_msg}, len(history)={len(history)}, history={json.dumps(messages_to_dict(history))}"
                )
                raise FailException(error_msg)

            # 7. Extend preset_messages with history
            preset_messages.extend(history)

        # 8. Append the current user message
        human_message = state["messages"][-1]
        preset_messages.append(HumanMessage(human_message.content))

        # 9. Replace the original user message with the composed preset + history + user messages
        return {
            "messages": [RemoveMessage(id=human_message.id), *preset_messages],
        }

    def _llm_node(self, state: AgentState) -> AgentState:
        """
        Override: LLM node for the tool-calling agent.

        If the model supports tool_call, use the parent implementation.
        Otherwise, use streaming text to detect whether the model is emitting
        ReACT-style JSON thoughts or direct messages.
        """
        # 1. If LLM supports tool_call, delegate to FunctionCallAgent
        if ModelFeature.TOOL_CALL in self.llm.features:
            return super()._llm_node(state)

        # 2. Check whether current agent iteration count exceeds limit
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
                ),
            )
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_END,
                ),
            )
            return {"messages": [AIMessage(MAX_ITERATION_RESPONSE)]}

        # 3. Extract LLM instance from agent config
        id = uuid.uuid4()
        start_at = time.perf_counter()
        llm = self.llm

        # 4. Variables to store streaming content
        gathered = None
        is_first_chunk = True
        generation_type = ""  # "message" or "thought"

        # 5. Stream from the LLM and decide whether it's JSON (tool call) or plain text
        for chunk in llm.stream(state["messages"]):
            # 6. Accumulate streaming chunks
            if is_first_chunk:
                gathered = chunk
                is_first_chunk = False
            else:
                gathered += chunk

            # 7. If we've already decided it's a message, publish streaming events
            if generation_type == "message":
                # 8. Extract chunk content and perform output moderation if needed
                review_config = self.agent_config.review_config
                content = chunk.content
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
                    ),
                )

            # 9. If we still haven't determined the generation type, infer it from the accumulated content
            if not generation_type:
                # 10. Only infer the type if length is at least 7 (length of "```json")
                if len(gathered.content.strip()) >= 7:
                    if gathered.content.strip().startswith("```json"):
                        generation_type = "thought"
                    else:
                        generation_type = "message"
                        # 11. Publish an event including the initial part of the message
                        self.agent_queue_manager.publish(
                            state["task_id"],
                            AgentThought(
                                id=id,
                                task_id=state["task_id"],
                                event=QueueEvent.AGENT_MESSAGE,
                                thought=gathered.content,
                                message=messages_to_dict(state["messages"]),
                                answer=gathered.content,
                                latency=(time.perf_counter() - start_at),
                            ),
                        )

        # 12. If generation_type is "thought", parse JSON and add an agent thought message
        if generation_type == "thought":
            try:
                # 13. Use regex to extract JSON; if parsing fails, treat it as a normal message
                pattern = r"^```json(.*?)```$"
                matches = re.findall(pattern, gathered.content, re.DOTALL)
                match_json = json.loads(matches[0])
                tool_calls = [{
                    "id": str(uuid.uuid4()),
                    "type": "tool_call",
                    "name": match_json.get("name", ""),
                    "args": match_json.get("args", {}),
                }]
                self.agent_queue_manager.publish(
                    state["task_id"],
                    AgentThought(
                        id=id,
                        task_id=state["task_id"],
                        event=QueueEvent.AGENT_THOUGHT,
                        thought=json.dumps(tool_calls),
                        message=messages_to_dict(state["messages"]),
                        latency=(time.perf_counter() - start_at),
                    ),
                )
                return {
                    "messages": [AIMessage(content="", tool_calls=tool_calls)],
                    "iteration_count": state["iteration_count"] + 1,
                }
            except Exception as _:
                generation_type = "message"
                self.agent_queue_manager.publish(
                    state["task_id"],
                    AgentThought(
                        id=id,
                        task_id=state["task_id"],
                        event=QueueEvent.AGENT_MESSAGE,
                        thought=gathered.content,
                        message=messages_to_dict(state["messages"]),
                        answer=gathered.content,
                        latency=(time.perf_counter() - start_at),
                    ),
                )

        # 14. If the final type is "message", we treat it as the final answer and stop
        if generation_type == "message":
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_END,
                ),
            )

        return {"messages": [gathered], "iteration_count": state["iteration_count"] + 1}
