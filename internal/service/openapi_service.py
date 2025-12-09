#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : openapi_service.py
"""
import json
from dataclasses import dataclass
from threading import Thread
from typing import Generator

from flask import current_app
from injector import inject
from langchain_core.messages import HumanMessage

from internal.core.agent.agents import FunctionCallAgent, ReACTAgent
from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.memory import TokenBufferMemory
from internal.entity.app_entity import AppStatus
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.entity.dataset_entity import RetrievalSource
from internal.exception import NotFoundException, ForbiddenException
from internal.model import Account, EndUser, Conversation, Message
from internal.schema.openapi_schema import OpenAPIChatReq
from pkg.response import Response
from pkg.sqlalchemy import SQLAlchemy
from .app_config_service import AppConfigService
from .app_service import AppService
from .base_service import BaseService
from .conversation_service import ConversationService
from .language_model_service import LanguageModelService
from .retrieval_service import RetrievalService
from ..core.language_model.entities.model_entity import ModelFeature


@inject
@dataclass
class OpenAPIService(BaseService):
    """Open API service."""
    db: SQLAlchemy
    app_service: AppService
    retrieval_service: RetrievalService
    app_config_service: AppConfigService
    conversation_service: ConversationService
    language_model_service: LanguageModelService

    def chat(self, req: OpenAPIChatReq, account: Account):
        """
        Start a chat conversation based on the incoming request and account information.
        The return value is either a chunked response or a generator for streaming.
        """
        # 1. Check whether the app belongs to the current account
        app = self.app_service.get_app(req.app_id.data, account)

        # 2. Check whether the app has been published
        if app.status != AppStatus.PUBLISHED:
            raise NotFoundException("The application does not exist or is not published. Please check and try again.")

        # 3. If an end_user_id is provided, verify that the end user belongs to the app
        if req.end_user_id.data:
            end_user = self.get(EndUser, req.end_user_id.data)
            if not end_user or end_user.app_id != app.id:
                raise ForbiddenException("The end user does not exist or does not belong to this application.")
        else:
            # 4. If no end user exists, create a new end user
            end_user = self.create(
                EndUser,
                **{"tenant_id": account.id, "app_id": app.id},
            )

        # 5. If a conversation_id is provided, verify that the conversation belongs to the app and end user
        if req.conversation_id.data:
            conversation = self.get(Conversation, req.conversation_id.data)
            if (
                    not conversation
                    or conversation.app_id != app.id
                    or conversation.invoke_from != InvokeFrom.SERVICE_API
                    or conversation.created_by != end_user.id
            ):
                raise ForbiddenException(
                    "The conversation does not exist, or it does not belong to the application/end user/invoke type."
                )
        else:
            # 6. If no conversation exists, create a new one
            conversation = self.create(Conversation, **{
                "app_id": app.id,
                "name": "New Conversation",
                "invoke_from": InvokeFrom.SERVICE_API,
                "created_by": end_user.id,
            })

        # 7. Get validated runtime configuration
        app_config = self.app_config_service.get_app_config(app)

        # 8. Create a new message record
        message = self.create(Message, **{
            "app_id": app.id,
            "conversation_id": conversation.id,
            "invoke_from": InvokeFrom.SERVICE_API,
            "created_by": end_user.id,
            "query": req.query.data,
            "status": MessageStatus.NORMAL,
        })

        # 9. Load language model instance based on model configuration
        llm = self.language_model_service.load_language_model(app_config.get("model_config", {}))

        # 10. Instantiate TokenBufferMemory to extract short-term memory
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=app_config["dialog_round"],
        )

        # 11. Convert tool configurations in the draft config into LangChain tools
        tools = self.app_config_service.get_langchain_tools_by_tools_config(app_config["tools"])

        # 12. Check whether a knowledge base is associated
        if app_config["datasets"]:
            # 13. Build a LangChain retrieval tool from the knowledge base
            dataset_retrieval = self.retrieval_service.create_langchain_tool_from_search(
                flask_app=current_app._get_current_object(),
                dataset_ids=[dataset["id"] for dataset in app_config["datasets"]],
                account_id=account.id,
                retrival_source=RetrievalSource.APP,
                **app_config["retrieval_config"],
            )
            tools.append(dataset_retrieval)

        # 14. Choose different Agents depending on whether the LLM supports tool calls
        agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL in llm.features else ReACTAgent
        agent = agent_class(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.DEBUGGER,
                preset_prompt=app_config["preset_prompt"],
                enable_long_term_memory=app_config["long_term_memory"]["enable"],
                tools=tools,
                review_config=app_config["review_config"],
            ),
        )

        # 15. Define base state for the agent
        agent_state = {
            "messages": [HumanMessage(req.query.data)],
            "history": history,
            "long_term_memory": conversation.summary,
        }

        # 16. Execute different logic depending on whether streaming is requested
        if req.stream.data is True:
            agent_thoughts_dict = {}

            def handle_stream() -> Generator:
                """
                Streaming event handler.
                In Python, any function that uses `yield` returns a generator.
                """
                for agent_thought in agent.stream(agent_state):
                    # Extract thought and answer
                    event_id = str(agent_thought.id)

                    # Fill agent_thought into agent_thoughts_dict for later persistence
                    if agent_thought.event != QueueEvent.PING:
                        # For AGENT_MESSAGE, we append/accumulate content; for others, we overwrite.
                        if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                            if event_id not in agent_thoughts_dict:
                                # Initialize agent message event
                                agent_thoughts_dict[event_id] = agent_thought
                            else:
                                # Accumulate agent message content
                                agent_thoughts_dict[event_id] = agent_thoughts_dict[event_id].model_copy(update={
                                    "thought": agent_thoughts_dict[event_id].thought + agent_thought.thought,
                                    "answer": agent_thoughts_dict[event_id].answer + agent_thought.answer,
                                    "latency": agent_thought.latency,
                                })
                        else:
                            # Handle other types of events
                            agent_thoughts_dict[event_id] = agent_thought

                    data = {
                        **agent_thought.model_dump(include={
                            "event", "thought", "observation", "tool", "tool_input", "answer", "latency",
                        }),
                        "id": event_id,
                        "end_user_id": str(end_user.id),
                        "conversation_id": str(conversation.id),
                        "message_id": str(message.id),
                        "task_id": str(agent_thought.task_id),
                    }
                    yield f"event: {agent_thought.event}\ndata:{json.dumps(data)}\n\n"

                # 22. Persist the message and reasoning process to the database
                thread = Thread(
                    target=self.conversation_service.save_agent_thoughts,
                    kwargs={
                        "flask_app": current_app._get_current_object(),
                        "account_id": account.id,
                        "app_id": app.id,
                        "app_config": app_config,
                        "conversation_id": conversation.id,
                        "message_id": message.id,
                        "agent_thoughts": [agent_thought for agent_thought in agent_thoughts_dict.values()],
                    }
                )
                thread.start()

            return handle_stream()

        # 17. Non-streaming (single-block) output
        agent_result = agent.invoke(agent_state)

        # 18. Persist the message and reasoning process to the database
        thread = Thread(
            target=self.conversation_service.save_agent_thoughts,
            kwargs={
                "flask_app": current_app._get_current_object(),
                "account_id": account.id,
                "app_id": app.id,
                "app_config": app_config,
                "conversation_id": conversation.id,
                "message_id": message.id,
                "agent_thoughts": agent_result.agent_thoughts,
            }
        )
        thread.start()

        return Response(data={
            "id": str(message.id),
            "end_user_id": str(end_user.id),
            "conversation_id": str(conversation.id),
            "query": req.query.data,
            "answer": agent_result.answer,
            "total_token_count": 0,
            "latency": agent_result.latency,
            "agent_thoughts": [{
                "id": str(agent_thought.id),
                "event": agent_thought.event,
                "thought": agent_thought.thought,
                "observation": agent_thought.observation,
                "tool": agent_thought.tool,
                "tool_input": agent_thought.tool_input,
                "latency": agent_thought.latency,
                "created_at": 0,
            } for agent_thought in agent_result.agent_thoughts]
        })
