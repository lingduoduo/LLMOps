#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : app_service.py
"""
import json
from dataclasses import dataclass
from datetime import datetime
from threading import Thread
from typing import Any, Generator
from uuid import UUID

from flask import request, current_app, Flask
from injector import inject
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from redis import Redis
from sqlalchemy import func, desc

from internal.core.agent.agents import FunctionCallAgent, AgentQueueManager
from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.memory import TokenBufferMemory
from internal.core.tools.api_tools.entities import ToolEntity
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.entity.app_entity import AppStatus, AppConfigType, DEFAULT_APP_CONFIG
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.entity.dataset_entity import RetrievalSource
from internal.exception import NotFoundException, ForbiddenException, ValidateErrorException, FailException
from internal.lib.helper import datetime_to_timestamp
from internal.model import (
    App,
    Account,
    AppConfigVersion,
    ApiTool,
    Dataset,
    AppConfig,
    AppDatasetJoin,
    Conversation,
    Message,
    MessageAgentThought,
)
from internal.schema.app_schema import (
    CreateAppReq,
    GetPublishHistoriesWithPageReq,
    GetDebugConversationMessagesWithPageReq,
)
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .conversation_service import ConversationService
from .retrieval_service import RetrievalService


@inject
@dataclass
class AppService(BaseService):
    """Application service logic"""
    db: SQLAlchemy
    redis_client: Redis
    conversation_service: ConversationService
    retrieval_service: RetrievalService
    api_provider_manager: ApiProviderManager
    builtin_provider_manager: BuiltinProviderManager

    def create_app(self, req: CreateAppReq, account: Account) -> App:
        """Create an Agent application"""
        # 1) Open an auto-commit database context
        with self.db.auto_commit():
            # 2) Create the app record and flush so we can get the app ID
            app = App(
                account_id=account.id,
                name=req.name.data,
                icon=req.icon.data,
                description=req.description.data,
                status=AppStatus.DRAFT,
            )
            self.db.session.add(app)
            self.db.session.flush()

            # 3) Add the draft configuration record
            app_config_version = AppConfigVersion(
                app_id=app.id,
                version=0,
                config_type=AppConfigType.DRAFT,
                **DEFAULT_APP_CONFIG,
            )
            self.db.session.add(app_config_version)
            self.db.session.flush()

            # 4) Link the draft configuration ID to the app
            app.draft_app_config_id = app_config_version.id

        # 5) Return the created app record
        return app

    def get_app(self, app_id: UUID, account: Account) -> App:
        """Get basic application information by ID"""
        # 1) Query the database for the app
        app = self.get(App, app_id)

        # 2) Check whether the app exists
        if not app:
            raise NotFoundException("The application does not exist, please verify and try again")

        # 3) Check whether the current account has permission to access the app
        if app.account_id != account.id:
            raise ForbiddenException("The current account has no permission to access this application")

        return app

    def get_draft_app_config(self, app_id: UUID, account: Account) -> dict[str, Any]:
        """Get the draft configuration of the specified application"""
        # 1) Get the app and validate permissions
        app = self.get_app(app_id, account)

        # 2) Get the app's draft configuration
        draft_app_config = app.draft_app_config

        # TODO: 3) Validate model_config when multi-LLM support is implemented

        # 4) Validate the tools list and remove tools that no longer exist
        draft_tools = draft_app_config.tools
        validate_tools = []
        tools = []
        for draft_tool in draft_tools:
            if draft_tool["type"] == "builtin_tool":
                # 5) Get builtin tool provider and ensure it exists
                provider = self.builtin_provider_manager.get_provider(draft_tool["provider_id"])
                if not provider:
                    continue

                # 6) Get tool entity from the provider and ensure it exists
                tool_entity = provider.get_tool_entity(draft_tool["tool_id"])
                if not tool_entity:
                    continue

                # 7) Check whether params in draft match the tool definition; reset to defaults if mismatched
                param_keys = set([param.name for param in tool_entity.params])
                params = draft_tool["params"]
                if set(draft_tool["params"].keys()) - param_keys:
                    params = {
                        param.name: param.default
                        for param in tool_entity.params
                        if param.default is not None
                    }

                # 8) All checks passed, append to validated tools
                validate_tools.append({**draft_tool, "params": params})

                # 9) Build builtin tool display information
                provider_entity = provider.provider_entity
                tools.append({
                    "type": "builtin_tool",
                    "provider": {
                        "id": provider_entity.name,
                        "name": provider_entity.name,
                        "label": provider_entity.label,
                        "icon": f"{request.scheme}://{request.host}/builtin-tools/{provider_entity.name}/icon",
                        "description": provider_entity.description,
                    },
                    "tool": {
                        "id": tool_entity.name,
                        "name": tool_entity.name,
                        "label": tool_entity.label,
                        "description": tool_entity.description,
                        "params": draft_tool["params"],
                    }
                })
            elif draft_tool["type"] == "api_tool":
                # 10) Query database for the API tool record and ensure it exists
                tool_record = self.db.session.query(ApiTool).filter(
                    ApiTool.provider_id == draft_tool["provider_id"],
                    ApiTool.name == draft_tool["tool_id"],
                ).one_or_none()
                if not tool_record:
                    continue

                # 11) Tool is valid; append to validated tools
                validate_tools.append(draft_tool)

                # 12) Build API tool display information
                provider = tool_record.provider
                tools.append({
                    "type": "api_tool",
                    "provider": {
                        "id": str(provider.id),
                        "name": provider.name,
                        "label": provider.name,
                        "icon": provider.icon,
                        "description": provider.description,
                    },
                    "tool": {
                        "id": str(tool_record.id),
                        "name": tool_record.name,
                        "label": tool_record.name,
                        "description": tool_record.description,
                        "params": {},
                    },
                })

        # 13) Determine whether the draft tool list needs to be updated
        if draft_tools != validate_tools:
            # 14) Update tools in the draft configuration
            self.update(draft_app_config, tools=validate_tools)

        # 15) Validate dataset list: remove datasets that no longer exist and collect metadata
        datasets = []
        draft_datasets = draft_app_config.datasets
        dataset_records = self.db.session.query(Dataset).filter(Dataset.id.in_(draft_datasets)).all()
        dataset_dict = {str(dataset_record.id): dataset_record for dataset_record in dataset_records}
        dataset_sets = set(dataset_dict.keys())

        # 16) Keep only dataset IDs that still exist (preserve original order)
        exist_dataset_ids = [dataset_id for dataset_id in draft_datasets if dataset_id in dataset_sets]

        # 17) If some datasets were deleted, update the draft configuration
        if set(exist_dataset_ids) != set(draft_datasets):
            self.update(draft_app_config, datasets=exist_dataset_ids)

        # 18) Build dataset display information
        for dataset_id in exist_dataset_ids:
            dataset = dataset_dict.get(str(dataset_id))
            datasets.append({
                "id": str(dataset.id),
                "name": dataset.name,
                "icon": dataset.icon,
                "description": dataset.description,
            })

        # TODO: 19) Validate workflow list when workflow module is implemented
        workflows = []

        # 20) Convert data to a dictionary and return
        return {
            "id": str(draft_app_config.id),
            "model_config": draft_app_config.model_config,
            "dialog_round": draft_app_config.dialog_round,
            "preset_prompt": draft_app_config.preset_prompt,
            "tools": tools,
            "workflows": workflows,
            "datasets": datasets,
            "retrieval_config": draft_app_config.retrieval_config,
            "long_term_memory": draft_app_config.long_term_memory,
            "opening_statement": draft_app_config.opening_statement,
            "opening_questions": draft_app_config.opening_questions,
            "speech_to_text": draft_app_config.speech_to_text,
            "text_to_speech": draft_app_config.text_to_speech,
            "review_config": draft_app_config.review_config,
            "updated_at": datetime_to_timestamp(draft_app_config.updated_at),
            "created_at": datetime_to_timestamp(draft_app_config.created_at),
        }

    def update_draft_app_config(
            self,
            app_id: UUID,
            draft_app_config: dict[str, Any],
            account: Account,
    ) -> AppConfigVersion:
        """Update the latest draft configuration of the specified application"""
        # 1) Get the app and validate permissions
        app = self.get_app(app_id, account)

        # 2) Validate the incoming draft configuration
        draft_app_config = self._validate_draft_app_config(draft_app_config, account)

        # 3) Get the latest draft configuration record for this app
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            # TODO: Because we currently use server_onupdate, we need to provide updated_at manually for now
            updated_at=datetime.now(),
            **draft_app_config,
        )

        return draft_app_config_record

    def publish_draft_app_config(self, app_id: UUID, account: Account) -> App:
        """Publish/update the draft configuration of the specified application as the runtime configuration"""
        # 1) Get app information and draft configuration
        app = self.get_app(app_id, account)
        draft_app_config = self.get_draft_app_config(app_id, account)

        # 2) Create the runtime configuration (do not delete historical runtime configs for now)
        app_config = self.create(
            AppConfig,
            app_id=app_id,
            model_config=draft_app_config["model_config"],
            dialog_round=draft_app_config["dialog_round"],
            preset_prompt=draft_app_config["preset_prompt"],
            tools=[
                {
                    "type": tool["type"],
                    "provider_id": tool["provider"]["id"],
                    "tool_id": tool["tool"]["name"],
                    "params": tool["tool"]["params"],
                }
                for tool in draft_app_config["tools"]
            ],
            # TODO: This may change when workflow module is completed
            workflows=draft_app_config["workflows"],
            retrieval_config=draft_app_config["retrieval_config"],
            long_term_memory=draft_app_config["long_term_memory"],
            opening_statement=draft_app_config["opening_statement"],
            opening_questions=draft_app_config["opening_questions"],
            speech_to_text=draft_app_config["speech_to_text"],
            text_to_speech=draft_app_config["text_to_speech"],
            review_config=draft_app_config["review_config"],
        )

        # 3) Update the app's linked runtime configuration and status
        self.update(app, app_config_id=app_config.id, status=AppStatus.PUBLISHED)

        # 4) First delete existing dataset associations
        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id,
            ).delete()

        # 5) Create new dataset association records
        for dataset in draft_app_config["datasets"]:
            self.create(AppDatasetJoin, app_id=app_id, dataset_id=dataset["id"])

        # 6) Copy the draft configuration and remove fields that should not be reused
        draft_app_config_copy = app.draft_app_config.__dict__.copy()
        remove_fields = ["id", "version", "config_type", "updated_at", "created_at", "_sa_instance_state"]
        for field in remove_fields:
            draft_app_config_copy.pop(field)

        # 7) Get the current maximum published version
        max_version = self.db.session.query(func.coalesce(func.max(AppConfigVersion.version), 0)).filter(
            AppConfigVersion.app_id == app_id,
            AppConfigVersion.config_type == AppConfigType.PUBLISHED,
        ).scalar()

        # 8) Create a new published history configuration
        self.create(
            AppConfigVersion,
            version=max_version + 1,
            config_type=AppConfigType.PUBLISHED,
            **draft_app_config_copy,
        )

        return app

    def cancel_publish_app_config(self, app_id: UUID, account: Account) -> App:
        """Cancel the published configuration of the specified application"""
        # 1) Get the app and validate permissions
        app = self.get_app(app_id, account)

        # 2) Ensure the app is currently in PUBLISHED state
        if app.status != AppStatus.PUBLISHED:
            raise FailException("The application has not been published, please verify and try again")

        # 3) Reset the app status to DRAFT and clear the runtime config ID
        self.update(app, status=AppStatus.DRAFT, app_config_id=None)

        # 4) Delete dataset associations for this app
        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id,
            ).delete()

        return app

    def get_publish_histories_with_page(
            self,
            app_id: UUID,
            req: GetPublishHistoriesWithPageReq,
            account: Account
    ) -> tuple[list[AppConfigVersion], Paginator]:
        """Get paginated list of published configuration histories for the specified application"""
        # 1) Validate app permissions
        self.get_app(app_id, account)

        # 2) Build paginator
        paginator = Paginator(db=self.db, req=req)

        # 3) Execute pagination and retrieve data
        app_config_versions = paginator.paginate(
            self.db.session.query(AppConfigVersion).filter(
                AppConfigVersion.app_id == app_id,
                AppConfigVersion.config_type == AppConfigType.PUBLISHED,
            ).order_by(desc("version"))
        )

        return app_config_versions, paginator

    def fallback_history_to_draft(
            self,
            app_id: UUID,
            app_config_version_id: UUID,
            account: Account,
    ) -> AppConfigVersion:
        """Revert a historical configuration version to the draft configuration"""
        # 1) Validate app permissions
        app = self.get_app(app_id, account)

        # 2) Get the specified historical configuration
        app_config_version = self.get(AppConfigVersion, app_config_version_id)
        if not app_config_version:
            raise NotFoundException("The historical configuration version does not exist, please verify and try again")

        # 3) Copy and clean the historical configuration (remove deleted tools, datasets, workflows, etc.)
        draft_app_config_dict = app_config_version.__dict__.copy()
        remove_fields = ["id", "app_id", "version", "config_type", "updated_at", "created_at", "_sa_instance_state"]
        for field in remove_fields:
            draft_app_config_dict.pop(field)

        # 4) Validate the historical configuration as a draft configuration
        draft_app_config_dict = self._validate_draft_app_config(draft_app_config_dict, account)

        # 5) Update the draft configuration record
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            # TODO: patch to update timestamp
            updated_at=datetime.now(),
            **draft_app_config_dict,
        )

        return draft_app_config_record

    def get_debug_conversation_summary(self, app_id: UUID, account: Account) -> str:
        """Get the long-term memory summary for the application's debug conversation"""
        # 1) Get the app and validate permissions
        app = self.get_app(app_id, account)

        # 2) Get the draft config and check whether long-term memory is enabled
        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("Long-term memory is not enabled for this application")

        return app.debug_conversation.summary

    def update_debug_conversation_summary(self, app_id: UUID, summary: str, account: Account) -> Conversation:
        """Update the long-term memory summary for the application's debug conversation"""
        # 1) Get the app and validate permissions
        app = self.get_app(app_id, account)

        # 2) Get the draft config and check whether long-term memory is enabled
        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("Long-term memory is not enabled for this application")

        # 3) Update the debug conversation summary
        debug_conversation = app.debug_conversation
        self.update(debug_conversation, summary=summary)

        return debug_conversation

    def delete_debug_conversation(self, app_id: UUID, account: Account) -> App:
        """Delete the debug conversation for the specified application"""
        # 1) Get the app and validate permissions
        app = self.get_app(app_id, account)

        # 2) If there is no debug_conversation_id, nothing to do
        if not app.debug_conversation_id:
            return app

        # 3) Reset debug_conversation_id to None
        self.update(app, debug_conversation_id=None)

        return app

    def debug_chat(self, app_id: UUID, query: str, account: Account) -> Generator:
        """Start a debug chat session for the specified application with the given query"""
        # 1) Get the app and validate permissions
        app = self.get_app(app_id, account)

        # 2) Get the latest draft configuration
        draft_app_config = self.get_draft_app_config(app_id, account)

        # 3) Get the app's debug conversation
        debug_conversation = app.debug_conversation

        # 4) Create a new message record
        message = self.create(
            Message,
            app_id=app_id,
            conversation_id=debug_conversation.id,
            created_by=account.id,
            query=query,
            status=MessageStatus.NORMAL,
        )

        # TODO: 5) Instantiate different LLMs based on model_config when multi-LLM support is added
        llm = ChatOpenAI(
            model=draft_app_config["model_config"]["model"],
            **draft_app_config["model_config"]["parameters"],
        )

        # 6) Instantiate TokenBufferMemory to extract short-term memory
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=debug_conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=draft_app_config["dialog_round"],
        )

        # 7) Convert draft tools to LangChain tools
        tools = []
        for tool in draft_app_config["tools"]:
            # 8) Handle different tool types
            if tool["type"] == "builtin_tool":
                # 9) For built-in tools, use builtin_provider_manager to get the tool instance
                builtin_tool = self.builtin_provider_manager.get_tool(
                    tool["provider"]["id"],
                    tool["tool"]["name"]
                )
                if not builtin_tool:
                    continue
                tools.append(builtin_tool(**tool["tool"]["params"]))
            else:
                # 10) For API tools, fetch ApiTool record and create the tool instance
                api_tool = self.get(ApiTool, tool["tool"]["id"])
                if not api_tool:
                    continue
                tools.append(
                    self.api_provider_manager.get_tool(
                        ToolEntity(
                            id=str(api_tool.id),
                            name=api_tool.name,
                            url=api_tool.url,
                            method=api_tool.method,
                            description=api_tool.description,
                            headers=api_tool.provider.headers,
                            parameters=api_tool.parameters,
                        )
                    )
                )

        # 11) Check whether datasets are associated
        if draft_app_config["datasets"]:
            # 12) Build a LangChain retrieval tool backed by the dataset(s)
            dataset_retrieval = self.retrieval_service.create_langchain_tool_from_search(
                flask_app=current_app._get_current_object(),
                dataset_ids=[dataset["id"] for dataset in draft_app_config["datasets"]],
                account_id=account.id,
                retrival_source=RetrievalSource.APP,
                **draft_app_config["retrieval_config"],
            )
            tools.append(dataset_retrieval)

        # TODO: 13) Build the Agent; currently we use FunctionCallAgent
        agent = FunctionCallAgent(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.DEBUGGER,
                enable_long_term_memory=draft_app_config["long_term_memory"]["enable"],
                tools=tools,
                review_config=draft_app_config["review_config"],
            ),
        )

        agent_thoughts = {}
        for agent_thought in agent.stream({
            "messages": [HumanMessage(query)],
            "history": history,
            "long_term_memory": debug_conversation.summary,
        }):
            # 15) Extract thought and answer
            event_id = str(agent_thought.id)

            # 17) Fill agent_thoughts for later persistence
            if agent_thought.event != QueueEvent.PING:
                # 18) Only AGENT_MESSAGE events accumulate text; others overwrite
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    if event_id not in agent_thoughts:
                        # 19) Initialize the agent message event
                        agent_thoughts[event_id] = {
                            "id": event_id,
                            "task_id": str(agent_thought.task_id),
                            "event": agent_thought.event,
                            "thought": agent_thought.thought,
                            "observation": agent_thought.observation,
                            "tool": agent_thought.tool,
                            "tool_input": agent_thought.tool_input,
                            "message": agent_thought.message,
                            "answer": agent_thought.answer,
                            "latency": agent_thought.latency,
                        }
                    else:
                        # 20) Accumulate agent message content
                        agent_thoughts[event_id] = {
                            **agent_thoughts[event_id],
                            "thought": agent_thoughts[event_id]["thought"] + agent_thought.thought,
                            "answer": agent_thoughts[event_id]["answer"] + agent_thought.answer,
                            "latency": agent_thought.latency,
                        }
                else:
                    # 21) Handle all other event types (overwrite)
                    agent_thoughts[event_id] = {
                        "id": event_id,
                        "task_id": str(agent_thought.task_id),
                        "event": agent_thought.event,
                        "thought": agent_thought.thought,
                        "observation": agent_thought.observation,
                        "tool": agent_thought.tool,
                        "tool_input": agent_thought.tool_input,
                        "message": agent_thought.message,
                        "answer": agent_thought.answer,
                        "latency": agent_thought.latency,
                    }

            data = {
                "id": event_id,
                "conversation_id": str(debug_conversation.id),
                "message_id": str(message.id),
                "task_id": str(agent_thought.task_id),
                "event": agent_thought.event,
                "thought": agent_thought.thought,
                "observation": agent_thought.observation,
                "tool": agent_thought.tool,
                "tool_input": agent_thought.tool_input,
                "answer": agent_thought.answer,
                "latency": agent_thought.latency,
            }
            yield f"event: {agent_thought.event}\ndata:{json.dumps(data)}\n\n"

        # 22) Persist the message and reasoning process in a background thread
        thread = Thread(
            target=self._save_agent_thoughts,
            kwargs={
                "flask_app": current_app._get_current_object(),
                "account_id": account.id,
                "app_id": app_id,
                "draft_app_config": draft_app_config,
                "conversation_id": debug_conversation.id,
                "message_id": message.id,
                "agent_thoughts": agent_thoughts,
            }
        )
        thread.start()

    def stop_debug_chat(self, app_id: UUID, task_id: UUID, account: Account) -> None:
        """Stop a debug chat session for the given app and task ID"""
        # 1) Validate app permissions
        self.get_app(app_id, account)

        # 2) Use the AgentQueueManager to stop the specified task
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.DEBUGGER, account.id)

    def get_debug_conversation_messages_with_page(
            self,
            app_id: UUID,
            req: GetDebugConversationMessagesWithPageReq,
            account: Account
    ) -> tuple[list[Message], Paginator]:
        """Get paginated debug conversation messages for the specified application"""
        # 1) Get the app and validate permissions
        app = self.get_app(app_id, account)

        # 2) Get the app's debug conversation
        debug_conversation = app.debug_conversation

        # 3) Build paginator and cursor filter conditions
        paginator = Paginator(db=self.db, req=req)
        filters = []
        if req.created_at.data:
            # 4) Convert timestamp to datetime
            created_at_datetime = datetime.fromtimestamp(req.created_at.data)
            filters.append(Message.created_at <= created_at_datetime)

        # 5) Execute pagination and query data
        messages = paginator.paginate(
            self.db.session.query(Message).filter(
                Message.conversation_id == debug_conversation.id,
                Message.status.in_([MessageStatus.STOP, MessageStatus.NORMAL]),
                Message.answer != "",
                *filters,
            ).order_by(desc("created_at"))
        )

        return messages, paginator

    def _save_agent_thoughts(
            self,
            flask_app: Flask,
            account_id: UUID,
            app_id: UUID,
            draft_app_config: dict[str, Any],
            conversation_id: UUID,
            message_id: UUID,
            agent_thoughts: dict[str, Any],
    ) -> None:
        """Persist agent reasoning steps to the database"""
        with flask_app.app_context():
            # 1) Initialize position and total latency
            position = 0
            latency = 0

            # 2) Re-query conversation and message in the worker thread so they are attached to this session
            conversation = self.get(Conversation, conversation_id)
            message = self.get(Message, message_id)

            # 3) Iterate over all reasoning steps and persist them
            for key, item in agent_thoughts.items():
                # 4) Store steps such as long-term memory recall, reasoning, messages, actions, and retrieval
                if item["event"] in [
                    QueueEvent.LONG_TERM_MEMORY_RECALL,
                    QueueEvent.AGENT_THOUGHT,
                    QueueEvent.AGENT_MESSAGE,
                    QueueEvent.AGENT_ACTION,
                    QueueEvent.DATASET_RETRIEVAL,
                ]:
                    # 5) Update position and total latency
                    position += 1
                    latency += item["latency"]

                    # 6) Create a MessageAgentThought record
                    self.create(
                        MessageAgentThought,
                        app_id=app_id,
                        conversation_id=conversation.id,
                        message_id=message.id,
                        invoke_from=InvokeFrom.DEBUGGER,
                        created_by=account_id,
                        position=position,
                        event=item["event"],
                        thought=item["thought"],
                        observation=item["observation"],
                        tool=item["tool"],
                        tool_input=item["tool_input"],
                        message=item["message"],
                        answer=item["answer"],
                        latency=item["latency"]
                    )

                # 7) Check if this event is AGENT_MESSAGE
                if item["event"] == QueueEvent.AGENT_MESSAGE:
                    # 8) Update message with final output and aggregated latency
                    self.update(
                        message,
                        message=item["message"],
                        answer=item["answer"],
                        latency=latency,
                    )

                    # 9) If long-term memory is enabled, update the conversation summary
                    if draft_app_config["long_term_memory"]["enable"]:
                        new_summary = self.conversation_service.summary(
                            message.query,
                            item["answer"],
                            conversation.summary
                        )
                        self.update(
                            conversation,
                            summary=new_summary,
                        )

                    # 10) Generate a conversation name for a new conversation
                    if conversation.is_nzew:
                        new_conversation_name = self.conversation_service.generate_conversation_name(message.query)
                        self.update(
                            conversation,
                            name=new_conversation_name,
                        )

                # 11) If the event is STOP or ERROR, update message status accordingly and break
                if item["event"] in [QueueEvent.STOP, QueueEvent.ERROR]:
                    self.update(
                        message,
                        status=MessageStatus.STOP if item["event"] == QueueEvent.STOP else MessageStatus.ERROR,
                        observation=item["observation"]
                    )
                    break

    def _validate_draft_app_config(self, draft_app_config: dict[str, Any], account: Account) -> dict[str, Any]:
        """Validate the provided draft configuration and return the sanitized result"""
        # 1) Validate that the draft config has at least one acceptable field to update
        acceptable_fields = [
            "model_config",
            "dialog_round",
            "preset_prompt",
            "tools",
            "workflows",
            "datasets",
            "retrieval_config",
            "long_term_memory",
            "opening_statement",
            "opening_questions",
            "speech_to_text",
            "text_to_speech",
            "review_config",
        ]

        # 2) Validate the top-level keys of the draft configuration
        if (
                not draft_app_config
                or not isinstance(draft_app_config, dict)
                or set(draft_app_config.keys()) - set(acceptable_fields)
        ):
            raise ValidateErrorException("Draft configuration fields are invalid, please verify and try again")

        # TODO: 3) Validate model_config when multi-LLM support is implemented

        # 4) Validate dialog_round (context turns)
        if "dialog_round" in draft_app_config:
            dialog_round = draft_app_config["dialog_round"]
            if (not isinstance(dialog_round, int)
                    or not (0 <= dialog_round <= 100)):
                raise ValidateErrorException("Dialog round count must be an integer between 0 and 100")

        # 5) Validate preset_prompt
        if "preset_prompt" in draft_app_config:
            preset_prompt = draft_app_config["preset_prompt"]
            if (not isinstance(preset_prompt, str)
                    or len(preset_prompt) > 2000):
                raise ValidateErrorException("Preset prompt must be a string of length 0–2000")

        # 6) Validate tools
        if "tools" in draft_app_config:
            tools = draft_app_config["tools"]
            validate_tools = []

            # 6.1 tools must be a list; empty list means no tools bound
            if not isinstance(tools, list):
                raise ValidateErrorException("Tools must be provided as a list")
            # 6.2 At most 5 tools can be bound
            if len(tools) > 5:
                raise ValidateErrorException("An Agent cannot be bound to more than 5 tools")
            # 6.3 Validate each tool
            for tool in tools:
                # 6.4 Tool must be non-empty and a dict
                if not tool or not isinstance(tool, dict):
                    raise ValidateErrorException("Bound tool configuration is invalid")
                # 6.5 Tool must have exactly: type, provider_id, tool_id, params
                if set(tool.keys()) != {"type", "provider_id", "tool_id", "params"}:
                    raise ValidateErrorException("Bound tool configuration is invalid")
                # 6.6 type must be builtin_tool or api_tool
                if tool["type"] not in ["builtin_tool", "api_tool"]:
                    raise ValidateErrorException("Bound tool configuration is invalid")
                # 6.7 provider_id and tool_id must be non-empty strings
                if (
                        not tool["provider_id"]
                        or not tool["tool_id"]
                        or not isinstance(tool["provider_id"], str)
                        or not isinstance(tool["tool_id"], str)
                ):
                    raise ValidateErrorException("Tool provider or tool identifier is invalid")
                # 6.8 params must be a dict
                if not isinstance(tool["params"], dict):
                    raise ValidateErrorException("Tool custom parameters must be provided as a dict")
                # 6.9 Check if the referenced tool exists, for builtin and api respectively
                if tool["type"] == "builtin_tool":
                    builtin_tool = self.builtin_provider_manager.get_tool(tool["provider_id"], tool["tool_id"])
                    if not builtin_tool:
                        continue
                else:
                    api_tool = self.db.session.query(ApiTool).filter(
                        ApiTool.provider_id == tool["provider_id"],
                        ApiTool.name == tool["tool_id"],
                        ApiTool.account_id == account.id,
                    ).one_or_none()
                    if not api_tool:
                        continue

                validate_tools.append(tool)

            # 6.10 Ensure there are no duplicate tools
            check_tools = [f"{tool['provider_id']}_{tool['tool_id']}" for tool in validate_tools]
            if len(set(check_tools)) != len(validate_tools):
                raise ValidateErrorException("Duplicate tools are bound")

            # 6.11 Replace tools with validated list
            draft_app_config["tools"] = validate_tools

        # TODO: 7) Validate workflows when workflow module is implemented
        if "workflows" in draft_app_config:
            draft_app_config["workflows"] = []

        # 8) Validate datasets (knowledge bases)
        if "datasets" in draft_app_config:
            datasets = draft_app_config["datasets"]

            # 8.1 datasets must be a list
            if not isinstance(datasets, list):
                raise ValidateErrorException("Dataset binding configuration is invalid")
            # 8.2 At most 5 datasets can be bound
            if len(datasets) > 5:
                raise ValidateErrorException("An Agent cannot be bound to more than 5 datasets")
            # 8.3 Validate each dataset ID
            for dataset_id in datasets:
                try:
                    UUID(dataset_id)
                except Exception:
                    raise ValidateErrorException("Dataset IDs must be valid UUIDs")
            # 8.4 Ensure no duplicates
            if len(set(datasets)) != len(datasets):
                raise ValidateErrorException("Duplicate datasets are bound")
            # 8.5 Check dataset ownership; keep only datasets belonging to the current account
            dataset_records = self.db.session.query(Dataset).filter(
                Dataset.id.in_(datasets),
                Dataset.account_id == account.id,
            ).all()
            dataset_sets = set([str(dataset_record.id) for dataset_record in dataset_records])
            draft_app_config["datasets"] = [dataset_id for dataset_id in datasets if dataset_id in dataset_sets]

        # 9) Validate retrieval_config
        if "retrieval_config" in draft_app_config:
            retrieval_config = draft_app_config["retrieval_config"]

            # 9.1 Non-empty dict
            if not retrieval_config or not isinstance(retrieval_config, dict):
                raise ValidateErrorException("Retrieval configuration is invalid")
            # 9.2 Keys must be exactly: retrieval_strategy, k, score
            if set(retrieval_config.keys()) != {"retrieval_strategy", "k", "score"}:
                raise ValidateErrorException("Retrieval configuration is invalid")
            # 9.3 Validate retrieval_strategy
            if retrieval_config["retrieval_strategy"] not in ["semantic", "full_text", "hybrid"]:
                raise ValidateErrorException("Retrieval strategy is invalid")
            # 9.4 Validate k
            if not isinstance(retrieval_config["k"], int) or not (0 <= retrieval_config["k"] <= 10):
                raise ValidateErrorException("The maximum number of retrieved documents must be 0–10")
            # 9.5 Validate score
            if not isinstance(retrieval_config["score"], float) or not (0 <= retrieval_config["score"] <= 1):
                raise ValidateErrorException("The minimum match score must be between 0 and 1")

        # 10) Validate long_term_memory configuration
        if "long_term_memory" in draft_app_config:
            long_term_memory = draft_app_config["long_term_memory"]

            # 10.1 Must be a non-empty dict
            if not long_term_memory or not isinstance(long_term_memory, dict):
                raise ValidateErrorException("Long-term memory configuration is invalid")
            # 10.2 Must only contain 'enable' and it must be bool
            if (
                    set(long_term_memory.keys()) != {"enable"}
                    or not isinstance(long_term_memory["enable"], bool)
            ):
                raise ValidateErrorException("Long-term memory configuration is invalid")

        # 11) Validate opening_statement
        if "opening_statement" in draft_app_config:
            opening_statement = draft_app_config["opening_statement"]

            # 11.1 Must be string, length ≤ 2000
            if not isinstance(opening_statement, str) or len(opening_statement) > 2000:
                raise ValidateErrorException("Opening statement length must be between 0 and 2000 characters")

        # 12) Validate opening_questions
        if "opening_questions" in draft_app_config:
            opening_questions = draft_app_config["opening_questions"]

            # 12.1 Must be a list with at most 3 items
            if not isinstance(opening_questions, list) or len(opening_questions) > 3:
                raise ValidateErrorException("There can be at most 3 opening questions")
            # 12.2 Each opening question must be a string
            for opening_question in opening_questions:
                if not isinstance(opening_question, str):
                    raise ValidateErrorException("Each opening question must be a string")

        # 13) Validate speech_to_text configuration
        if "speech_to_text" in draft_app_config:
            speech_to_text = draft_app_config["speech_to_text"]

            # 13.1 Must be a non-empty dict
            if not speech_to_text or not isinstance(speech_to_text, dict):
                raise ValidateErrorException("Speech-to-text configuration is invalid")
            # 13.2 Must only contain 'enable' as bool
            if (
                    set(speech_to_text.keys()) != {"enable"}
                    or not isinstance(speech_to_text["enable"], bool)
            ):
                raise ValidateErrorException("Speech-to-text configuration is invalid")

        # 14) Validate text_to_speech configuration
        if "text_to_speech" in draft_app_config:
            text_to_speech = draft_app_config["text_to_speech"]

            # 14.1 Must be a dict
            if not isinstance(text_to_speech, dict):
                raise ValidateErrorException("Text-to-speech configuration is invalid")
            # 14.2 Validate keys and types
            if (
                    set(text_to_speech.keys()) != {"enable", "voice", "auto_play"}
                    or not isinstance(text_to_speech["enable"], bool)
                    # TODO: Add more voices when multimodal Agents are implemented
                    or text_to_speech["voice"] not in ["echo"]
                    or not isinstance(text_to_speech["auto_play"], bool)
            ):
                raise ValidateErrorException("Text-to-speech configuration is invalid")

        # 15) Validate review_config
        if "review_config" in draft_app_config:
            review_config = draft_app_config["review_config"]

            # 15.1 Must be a non-empty dict
            if not review_config or not isinstance(review_config, dict):
                raise ValidateErrorException("Review configuration is invalid")
            # 15.2 Must contain: enable, keywords, inputs_config, outputs_config
            if set(review_config.keys()) != {"enable", "keywords", "inputs_config", "outputs_config"}:
                raise ValidateErrorException("Review configuration is invalid")
            # 15.3 Validate enable
            if not isinstance(review_config["enable"], bool):
                raise ValidateErrorException("review.enable must be a boolean")
            # 15.4 Validate keywords
            if (
                    not isinstance(review_config["keywords"], list)
                    or (review_config["enable"] and len(review_config["keywords"]) == 0)
                    or len(review_config["keywords"]) > 100
            ):
                raise ValidateErrorException("review.keywords must be non-empty and at most 100 when review is enabled")
            for keyword in review_config["keywords"]:
                if not isinstance(keyword, str):
                    raise ValidateErrorException("Each review.keyword must be a string")
            # 15.5 Validate inputs_config
            if (
                    not review_config["inputs_config"]
                    or not isinstance(review_config["inputs_config"], dict)
                    or set(review_config["inputs_config"].keys()) != {"enable", "preset_response"}
                    or not isinstance(review_config["inputs_config"]["enable"], bool)
                    or not isinstance(review_config["inputs_config"]["preset_response"], str)
            ):
                raise ValidateErrorException("review.inputs_config must be a dict with valid fields")
            # 15.6 Validate outputs_config
            if (
                    not review_config["outputs_config"]
                    or not isinstance(review_config["outputs_config"], dict)
                    or set(review_config["outputs_config"].keys()) != {"enable"}
                    or not isinstance(review_config["outputs_config"]["enable"], bool)
            ):
                raise ValidateErrorException("review.outputs_config must be a dict with valid fields")
            # 15.7 When review is enabled, at least one of inputs_config or outputs_config must be enabled
            if review_config["enable"]:
                if (
                        review_config["inputs_config"]["enable"] is False
                        and review_config["outputs_config"]["enable"] is False
                ):
                    raise ValidateErrorException("Input review and output review must enable at least one option")

                if (
                        review_config["inputs_config"]["enable"]
                        and review_config["inputs_config"]["preset_response"].strip() == ""
                ):
                    raise ValidateErrorException("Preset response for input review cannot be empty")

        return draft_app_config
