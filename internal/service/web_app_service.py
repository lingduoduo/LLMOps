#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : web_app_service.py
"""
import json
from dataclasses import dataclass
from typing import Generator
from uuid import UUID

from flask import current_app
from injector import inject
from langchain_core.messages import HumanMessage
from sqlalchemy import desc

from internal.core.agent.agents import FunctionCallAgent, ReACTAgent, AgentQueueManager
from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.core.memory import TokenBufferMemory
from internal.entity.app_entity import AppStatus
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.entity.dataset_entity import RetrievalSource
from internal.exception import NotFoundException, ForbiddenException
from internal.model import App, Account, Conversation, Message
from internal.schema.web_app_schema import WebAppChatReq
from pkg.sqlalchemy import SQLAlchemy
from .app_config_service import AppConfigService
from .base_service import BaseService
from .conversation_service import ConversationService
from .language_model_service import LanguageModelService
from .retrieval_service import RetrievalService


@inject
@dataclass
class WebAppService(BaseService):
    """WebApp service."""
    db: SQLAlchemy
    app_config_service: AppConfigService
    retrieval_service: RetrievalService
    conversation_service: ConversationService
    language_model_service: LanguageModelService

    def get_web_app(self, token: str) -> App:
        """Get a WebApp instance by token."""
        # 1. Query the database for the app associated with the token
        app = self.db.session.query(App).filter(
            App.token == token,
        ).one_or_none()
        if not app or app.status != AppStatus.PUBLISHED:
            raise NotFoundException("The WebApp does not exist or is not published. Please verify and try again.")

        # 2. Return the matched app
        return app

    def web_app_chat(self, token: str, req: WebAppChatReq, account: Account) -> Generator:
        """Chat with the specified WebApp using the token and request payload."""
        # 1. Fetch and validate the WebApp (must be published)
        app = self.get_web_app(token)

        # 2. If a conversation ID is provided, validate ownership and invocation source
        if req.conversation_id.data:
            conversation = self.get(Conversation, req.conversation_id.data)
            if (
                    not conversation
                    or conversation.app_id != app.id
                    or conversation.invoke_from != InvokeFrom.WEB_APP
                    or conversation.created_by != account.id
                    or conversation.is_deleted is True
            ):
                raise ForbiddenException(
                    "The conversation does not exist, or does not belong to the current app/user/invocation source.")
        else:
            # 3. If no conversation_id is provided, create a new conversation
            conversation = self.create(Conversation, **{
                "app_id": app.id,
                "name": "New Conversation",
                "invoke_from": InvokeFrom.WEB_APP,
                "created_by": account.id,
            })

        # 4. Load and validate runtime configuration
        app_config = self.app_config_service.get_app_config(app)

        # 5. Create a new message record
        message = self.create(
            Message,
            app_id=app.id,
            conversation_id=conversation.id,
            invoke_from=InvokeFrom.WEB_APP,
            created_by=account.id,
            query=req.query.data,
            status=MessageStatus.NORMAL,
        )

        # 6. Load the LLM instance from the language model service/manager
        llm = self.language_model_service.load_language_model(app_config.get("model_config", {}))

        # 7. Instantiate TokenBufferMemory to extract short-term memory
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=app_config["dialog_round"],
        )

        # 8. Convert tool configs into LangChain tools
        tools = self.app_config_service.get_langchain_tools_by_tools_config(app_config["tools"])

        # 9. Check whether any datasets are attached
        if app_config["datasets"]:
            # 10. Build a dataset retrieval tool and append it to the tools list
            dataset_retrieval = self.retrieval_service.create_langchain_tool_from_search(
                flask_app=current_app._get_current_object(),
                dataset_ids=[dataset["id"] for dataset in app_config["datasets"]],
                account_id=account.id,
                retrival_source=RetrievalSource.APP,
                **app_config["retrieval_config"],
            )
            tools.append(dataset_retrieval)

        # 11. If workflows are attached, convert them into tools and add them to the tools list
        if app_config["workflows"]:
            workflow_tools = self.app_config_service.get_langchain_tools_by_workflow_ids(
                [workflow["id"] for workflow in app_config["workflows"]]
            )
            tools.extend(workflow_tools)

        # 12. Choose the agent implementation based on whether the LLM supports tool calling
        agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL in llm.features else ReACTAgent
        agent = agent_class(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.WEB_APP,
                preset_prompt=app_config["preset_prompt"],
                enable_long_term_memory=app_config["long_term_memory"]["enable"],
                tools=tools,
                review_config=app_config["review_config"],
            ),
        )

        # 13. Store reasoning traces in a dict and stream agent output
        agent_thoughts = {}
        for agent_thought in agent.stream({
            "messages": [HumanMessage(req.query.data)],
            "history": history,
            "long_term_memory": conversation.summary,
        }):
            # 14. Extract thought and answer
            event_id = str(agent_thought.id)

            # 15. Populate agent_thought so it can be persisted later
            if agent_thought.event != QueueEvent.PING:
                # 16. Only AGENT_MESSAGE is accumulated; everything else is overwritten
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    if event_id not in agent_thoughts:
                        # 17. Initialize an agent message event
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 18. Accumulate partial agent messages
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(update={
                            "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                            # Message-related fields
                            "message": agent_thought.message,
                            "message_token_count": agent_thought.message_token_count,
                            "message_unit_price": agent_thought.message_unit_price,
                            "message_price_unit": agent_thought.message_price_unit,
                            # Answer-related fields
                            "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                            "answer_token_count": agent_thought.answer_token_count,
                            "answer_unit_price": agent_thought.answer_unit_price,
                            "answer_price_unit": agent_thought.answer_price_unit,
                            # Agent stats
                            "total_token_count": agent_thought.total_token_count,
                            "total_price": agent_thought.total_price,
                            "latency": agent_thought.latency,
                        })
                else:
                    # 19. Handle other event types
                    agent_thoughts[event_id] = agent_thought
            data = {
                **agent_thought.model_dump(include={
                    "event", "thought", "observation", "tool", "tool_input", "answer",
                    "total_token_count", "total_price", "latency",
                }),
                "id": event_id,
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "task_id": str(agent_thought.task_id),
            }
            yield f"event: {agent_thought.event}\ndata:{json.dumps(data)}\n\n"

        # 20. Persist the message and reasoning traces
        self.conversation_service.save_agent_thoughts(
            account_id=account.id,
            app_id=app.id,
            app_config=app_config,
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=[agent_thought for agent_thought in agent_thoughts.values()],
        )

    def stop_web_app_chat(self, token: str, task_id: UUID, account: Account):
        """Stop an ongoing WebApp chat by token and task_id."""
        # 1. Fetch and validate the WebApp (must be published)
        self.get_web_app(token)

        # 2. Ask AgentQueueManager to stop the specific task
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.WEB_APP, account.id)

    def get_conversations(self, token: str, is_pinned: bool, account: Account) -> list[Conversation]:
        """Get the conversation list for an account under the specified WebApp, filtered by pinned status."""
        # 1. Fetch and validate the WebApp (must be published)
        app = self.get_web_app(token)

        # 2. Filter and query conversations
        conversations = self.db.session.query(Conversation).filter(
            Conversation.app_id == app.id,
            Conversation.created_by == account.id,
            Conversation.invoke_from == InvokeFrom.WEB_APP,
            Conversation.is_pinned == is_pinned,
            ~Conversation.is_deleted,
        ).order_by(desc("created_at")).all()

        return conversations
