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
    REACT_AGENT_SYSTEM_PROMPT_TEMPLATE,
    MAX_ITERATION_RESPONSE,
)
from internal.core.agent.entities.queue_entity import QueueEvent, AgentThought
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.exception import FailException
from .function_call_agent import FunctionCallAgent


class ReACTAgent(FunctionCallAgent):
    """Agent based on ReACT-style reasoning, inheriting from FunctionCallAgent and
    overriding the long_term_memory_node and llm_node nodes.
    """

    def _long_term_memory_recall_node(self, state: AgentState) -> AgentState:
        """Override long-term memory recall node; use prompts to simulate tool calls
        and enforce structured output.
        """
        # 1. Check whether tool calling is supported; if so, reuse the
        #    long-term memory recall node from the function-call agent.
        if ModelFeature.TOOL_CALL in self.llm.features:
            return super()._long_term_memory_recall_node(state)

        # 2. Determine whether we need to recall long-term memory based on agent config
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

        # 3. If AGENT_THOUGHT is not supported, use the basic prompt without tool descriptions
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
            # 4. If reasoning is supported, use REACT_AGENT_SYSTEM_PROMPT_TEMPLATE
            #    and include tool descriptions
            preset_messages = [
                SystemMessage(
                    REACT_AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                        preset_prompt=self.agent_config.preset_prompt,
                        long_term_memory=long_term_memory,
                        tool_description=render_text_description_and_args(self.agent_config.tools),
                    )
                )
            ]

        # 5. Append short-term history to the message list
        history = state["history"]
        if isinstance(history, list) and len(history) > 0:
            # 6. Validate that the history is in alternating format:
            #    [human, ai, human, ai, ...]
            if len(history) % 2 != 0:
                self.agent_queue_manager.publish_error(
                    state["task_id"], "Invalid agent message history format"
                )
                logging.exception(
                    f"Invalid agent message history format, "
                    f"len(history)={len(history)}, "
                    f"history={json.dumps(messages_to_dict(history))}"
                )
                raise FailException("Invalid agent message history format")
            # 7. Append history to preset messages
            preset_messages.extend(history)

        # 8. Append the current user query
        human_message = state["messages"][-1]
        preset_messages.append(HumanMessage(human_message.content))

        # 9. Replace the original user message with the constructed preset messages
        return {
            "messages": [RemoveMessage(id=human_message.id), *preset_messages],
        }

    def _llm_node(self, state: AgentState) -> AgentState:
        """Override LLM node for an agent that simulates tool calls via ReACT."""
        # 1. If the current LLM supports tool_call, delegate to FunctionCallAgent._llm_node
        if ModelFeature.TOOL_CALL in self.llm.features:
            return super()._llm_node(state)

        # 2. Check whether the current iteration count exceeds the configured maximum
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

        # 3. Get the LLM from agent config
        id = uuid.uuid4()
        start_at = time.perf_counter()
        llm = self.llm

        # 4. Variables to store streamed output
        gathered = None
        is_first_chunk = True
        generation_type = ""

        # 5. Stream from the LLM and detect whether the output starts with ```json
        #    to distinguish between tool calls and plain text.
        for chunk in llm.stream(state["messages"]):
            # 6. Accumulate streamed chunks
            if is_first_chunk:
                gathered = chunk
                is_first_chunk = False
            else:
                gathered += chunk

            # 7. If generation type is plain message, publish agent message events
            if generation_type == "message":
                # 8. Extract chunk content and apply output review if enabled
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

            # 9. If generation type is not yet determined, figure out whether this
            #    is a tool call or a plain message
            if not generation_type:
                # 10. Only determine type when the content length is at least 7,
                #     which is the length of "```json"
                if len(gathered.content.strip()) >= 7:
                    if gathered.content.strip().startswith("```json"):
                        generation_type = "thought"
                    else:
                        generation_type = "message"
                        # 11. Publish an event immediately so no initial characters are lost
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

        # 8. Compute total input + output token counts
        input_token_count = self.llm.get_num_tokens_from_messages(state["messages"])
        output_token_count = self.llm.get_num_tokens_from_messages([gathered])

        # 9. Get input/output prices and pricing unit
        input_price, output_price, unit = self.llm.get_pricing()

        # 10. Compute total tokens and total cost
        total_token_count = input_token_count + output_token_count
        total_price = (input_token_count * input_price + output_token_count * output_price) * unit

        # 12. If the type is "thought", parse the JSON and construct a tool-call message
        if generation_type == "thought":
            try:
                # 13. Parse the JSON content via regex; if it fails, treat as normal text
                pattern = r"^```json(.*?)```$"
                matches = re.findall(pattern, gathered.content, re.DOTALL)
                match_json = json.loads(matches[0])
                tool_calls = [
                    {
                        "id": str(uuid.uuid4()),
                        "type": "tool_call",
                        "name": match_json.get("name", ""),
                        "args": match_json.get("args", {}),
                    }
                ]
                self.agent_queue_manager.publish(
                    state["task_id"],
                    AgentThought(
                        id=id,
                        task_id=state["task_id"],
                        event=QueueEvent.AGENT_THOUGHT,
                        thought=json.dumps(gathered.tool_calls),
                        # Message-related fields
                        message=messages_to_dict(state["messages"]),
                        message_token_count=input_token_count,
                        message_unit_price=input_price,
                        message_price_unit=unit,
                        # Answer-related fields
                        answer="",
                        answer_token_count=output_token_count,
                        answer_unit_price=output_price,
                        answer_price_unit=unit,
                        # Agent reasoning statistics
                        total_token_count=total_token_count,
                        total_price=total_price,
                        latency=(time.perf_counter() - start_at),
                    ),
                )
                return {
                    "messages": [AIMessage(content="", tool_calls=tool_calls)],
                    "iteration_count": state["iteration_count"] + 1,
                }
            except Exception:
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

        # 14. If the final type is "message", we already have the final answer.
        #     Publish an empty message to record token/cost stats and end the agent.
        if generation_type == "message":
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=id,
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_MESSAGE,
                    thought="",
                    # Message-related fields
                    message=messages_to_dict(state["messages"]),
                    message_token_count=input_token_count,
                    message_unit_price=input_price,
                    message_price_unit=unit,
                    # Answer-related fields
                    answer="",
                    answer_token_count=output_token_count,
                    answer_unit_price=output_price,
                    answer_price_unit=unit,
                    # Agent reasoning statistics
                    total_token_count=total_token_count,
                    total_price=total_price,
                    latency=(time.perf_counter() - start_at),
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

        return {"messages": [gathered], "iteration_count": state["iteration_count"] + 1}
