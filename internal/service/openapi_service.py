#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/11/19 22:21
@Author  : thezehui@gmail.com
@File    : openapi_service.py
"""
import json
from dataclasses import dataclass
from threading import Thread
from typing import Generator

from flask import current_app
from injector import inject
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from internal.core.agent.agents import FunctionCallAgent
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
from .retrieval_service import RetrievalService


@inject
@dataclass
class OpenAPIService(BaseService):
    """OpenAPI Service"""
    db: SQLAlchemy
    app_service: AppService
    retrieval_service: RetrievalService
    app_config_service: AppConfigService
    conversation_service: ConversationService

    def chat(self, req: OpenAPIChatReq, account: Account):
        """
        Initiate a chat conversation based on the request and account info.
        Returns either a streaming generator or chunked data response.
        """

        # 1. Check whether the app belongs to the current account
        app = self.app_service.get_app(req.app_id.data, account)

        # 2. Check whether the app is published
        if app.status != AppStatus.PUBLISHED:
            raise NotFoundException("The application does not exist or is not published.")

        # 3. If an end_user_id is provided, validate that the user belongs to this app
        if req.end_user_id.data:
            end_user = self.get(EndUser, req.end_user_id.data)
            if not end_user or end_user.app_id != app.id:
                raise ForbiddenException("End user does not exist or does not belong to this application.")
        else:
            # 4. Otherwise create a new end user
            end_user = self.create(
                EndUser,
                **{"tenant_id": account.id, "app_id": app.id},
            )

        # 5. If a conversation_id is provided, verify ownership
        if req.conversation_id.data:
            conversation = self.get(Conversation, req.conversation_id.data)
            if (
                    not conversation
                    or conversation.app_id != app.id
                    or conversation.invoke_from != InvokeFrom.SERVICE_API
                    or conversation.created_by != end_user.id
            ):
                raise ForbiddenException("Conversation does not exist or does not belong to this app/end user/API.")
        else:
            # 6. Otherwise create a new conversation
            conversation = self.create(Conversation, **{
                "app_id": app.id,
                "name": "New Conversation",
                "invoke_from": InvokeFrom.SERVICE_API,
                "created_by": end_user.id,
            })

        # 7. Retrieve validated runtime configuration
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

        # TODO: 9. Instantiate the LLM according to model_config;
        #       this will be modified when supporting multiple LLM providers.
        llm = ChatOpenAI(
            model=app_config["model_config"]["model"],
            **app_config["model_config"]["parameters"],
        )

        # 10. TokenBufferMemory extracts short-term conversational memory
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=app_config["dialog_round"],
        )

        # 11. Convert tool configuration into LangChain tools
        tools = self.app_config_service.get_langchain_tools_by_tools_config(app_config["tools"])

        # 12. If the app is linked with datasets
        if app_config["datasets"]:
            # 13. Construct a LangChain retriever tool
            dataset_retrieval = self.retrieval_service.create_langchain_tool_from_search(
                flask_app=current_app._get_current_object(),
                dataset_ids=[dataset["id"] for dataset in app_config["datasets"]],
                account_id=account.id,
                retrival_source=RetrievalSource.APP,
                **app_config["retrieval_config"],
            )
            tools.append(dataset_retrieval)

        # TODO: 14. Construct an intelligent agent (currently using FunctionCallAgent)
        agent = FunctionCallAgent(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.DEBUGGER,
                enable_long_term_memory=app_config["long_term_memory"]["enable"],
                tools=tools,
                review_config=app_config["review_config"],
            ),
        )

        # 15. Define initial agent state
        agent_state = {
            "messages": [HumanMessage(req.query.data)],
            "history": history,
            "long_term_memory": conversation.summary,
        }

        # 16. Stream mode
        if req.stream.data is True:
            agent_thoughts_dict = {}

            def handle_stream() -> Generator:
                """Streaming event handler. Any function using yield returns a generator."""
                for agent_thought in agent.stream(agent_state):
                    event_id = str(agent_thought.id)

                    # Aggregate thought and answer content for AGENT_MESSAGE events
                    if agent_thought.event != QueueEvent.PING:
                        if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                            if event_id not in agent_thoughts_dict:
                                agent_thoughts_dict[event_id] = agent_thought
                            else:
                                # Append incremental thoughts & answers
                                agent_thoughts_dict[event_id] = agent_thoughts_dict[event_id].model_copy(update={
                                    "thought": agent_thoughts_dict[event_id].thought + agent_thought.thought,
                                    "answer": agent_thoughts_dict[event_id].answer + agent_thought.answer,
                                    "latency": agent_thought.latency,
                                })
                        else:
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

                # 22. Save thoughts to the DB in an async thread
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

        # 17. Non-stream mode → get agent result directly
        agent_result = agent.invoke(agent_state)

        # 18. Save result to database in a background thread
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
