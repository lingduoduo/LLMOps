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

from flask import current_app
from injector import inject
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from redis import Redis
from sqlalchemy import func, desc

from internal.core.agent.agents import FunctionCallAgent, AgentQueueManager
from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.memory import TokenBufferMemory
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.entity.app_entity import AppStatus, AppConfigType, DEFAULT_APP_CONFIG
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.entity.dataset_entity import RetrievalSource
from internal.exception import NotFoundException, ForbiddenException, ValidateErrorException, FailException
from internal.lib.helper import remove_fields
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
)
from internal.schema.app_schema import (
    CreateAppReq,
    GetAppsWithPageReq,
    GetPublishHistoriesWithPageReq,
    GetDebugConversationMessagesWithPageReq,
)
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .app_config_service import AppConfigService
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
    app_config_service: AppConfigService
    api_provider_manager: ApiProviderManager
    builtin_provider_manager: BuiltinProviderManager

    def create_app(self, req: CreateAppReq, account: Account) -> App:
        """Create an Agent application"""
        # 1. Open an auto-commit DB context
        with self.db.auto_commit():
            # 2. Create an app record and flush to get the app ID
            app = App(
                account_id=account.id,
                name=req.name.data,
                icon=req.icon.data,
                description=req.description.data,
                status=AppStatus.DRAFT,
            )
            self.db.session.add(app)
            self.db.session.flush()

            # 3. Add an initial draft config record
            app_config_version = AppConfigVersion(
                app_id=app.id,
                version=0,
                config_type=AppConfigType.DRAFT,
                **DEFAULT_APP_CONFIG,
            )
            self.db.session.add(app_config_version)
            self.db.session.flush()

            # 4. Attach the draft config ID to the app
            app.draft_app_config_id = app_config_version.id

        # 5. Return the created app
        return app

    def get_app(self, app_id: UUID, account: Account) -> App:
        """Get basic app info by ID"""
        # 1. Query the DB for the app
        app = self.get(App, app_id)

        # 2. Check if the app exists
        if not app:
            raise NotFoundException("The application does not exist, please verify and try again.")

        # 3. Check whether the current account has permission to access this app
        if app.account_id != account.id:
            raise ForbiddenException(
                "The current account has no permission to access this application. Please verify and try again.")

        return app

    def delete_app(self, app_id: UUID, account: Account) -> App:
        """Delete an app by app ID + account. For now, only delete the basic app info."""
        app = self.get_app(app_id, account)
        self.delete(app)
        return app

    def update_app(self, app_id: UUID, account: Account, **kwargs) -> App:
        """Update the specified app based on app ID + account + payload"""
        app = self.get_app(app_id, account)
        self.update(app, **kwargs)
        return app

    def copy_app(self, app_id: UUID, account: Account) -> App:
        """Copy an Agent app by ID and create a new Agent with the same settings"""
        # 1. Get the app + draft config and validate permissions
        app = self.get_app(app_id, account)
        draft_app_config = app.draft_app_config

        # 2. Convert ORM objects to dict and strip unused fields
        app_dict = app.__dict__.copy()
        draft_app_config_dict = draft_app_config.__dict__.copy()

        # 3. Remove fields that should not be copied
        app_remove_fields = [
            "id", "app_config_id", "draft_app_config_id", "debug_conversation_id",
            "status", "updated_at", "created_at", "_sa_instance_state",
        ]
        draft_app_config_remove_fields = [
            "id", "app_id", "version", "updated_at", "created_at", "_sa_instance_state",
        ]
        remove_fields(app_dict, app_remove_fields)
        remove_fields(draft_app_config_dict, draft_app_config_remove_fields)

        # 4. Open an auto-commit DB context
        with self.db.auto_commit():
            # 5. Create a new app record
            new_app = App(**app_dict, status=AppStatus.DRAFT)
            self.db.session.add(new_app)
            self.db.session.flush()

            # 6. Add a draft config for the new app
            new_draft_app_config = AppConfigVersion(
                **draft_app_config_dict,
                app_id=new_app.id,
                version=0,
            )
            self.db.session.add(new_draft_app_config)
            self.db.session.flush()

            # 7. Update the app’s draft config ID
            new_app.draft_app_config_id = new_draft_app_config.id

        # 8. Return the newly created app
        return new_app

    def get_apps_with_page(self, req: GetAppsWithPageReq, account: Account) -> tuple[list[App], Paginator]:
        """Get a paginated list of apps under the current logged-in account"""
        # 1. Build paginator
        paginator = Paginator(db=self.db, req=req)

        # 2. Build filter conditions
        filters = [App.account_id == account.id]
        if req.search_word.data:
            filters.append(App.name.ilike(f"%{req.search_word.data}%"))

        # 3. Execute pagination query
        apps = paginator.paginate(
            self.db.session.query(App).filter(*filters).order_by(desc("created_at"))
        )

        return apps, paginator

    def get_draft_app_config(self, app_id: UUID, account: Account) -> dict[str, Any]:
        """Get the draft config for a specified app ID"""
        app = self.get_app(app_id, account)
        return self.app_config_service.get_draft_app_config(app)

    def update_draft_app_config(
            self,
            app_id: UUID,
            draft_app_config: dict[str, Any],
            account: Account,
    ) -> AppConfigVersion:
        """Update the latest draft config of the specified app"""
        # 1. Get app info and validate permissions
        app = self.get_app(app_id, account)

        # 2. Validate the passed draft config
        draft_app_config = self._validate_draft_app_config(draft_app_config, account)

        # 3. Get the current draft config record of the app
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            # todo: Because we currently use server_onupdate, we temporarily pass updated_at manually
            updated_at=datetime.now(),
            **draft_app_config,
        )

        return draft_app_config_record

    def publish_draft_app_config(self, app_id: UUID, account: Account) -> App:
        """Publish/update the draft config of an app to its runtime config"""
        # 1. Get app and draft config
        app = self.get_app(app_id, account)
        draft_app_config = self.get_draft_app_config(app_id, account)

        # 2. Create a runtime application config (for now we don't delete older runtime configs)
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
            # todo: Will be updated after the workflow module is finished
            workflows=draft_app_config["workflows"],
            retrieval_config=draft_app_config["retrieval_config"],
            long_term_memory=draft_app_config["long_term_memory"],
            opening_statement=draft_app_config["opening_statement"],
            opening_questions=draft_app_config["opening_questions"],
            speech_to_text=draft_app_config["speech_to_text"],
            text_to_speech=draft_app_config["text_to_speech"],
            suggested_after_answer=draft_app_config["suggested_after_answer"],
            review_config=draft_app_config["review_config"],
        )

        # 3. Update app's runtime config and status
        self.update(app, app_config_id=app_config.id, status=AppStatus.PUBLISHED)

        # 4. First delete existing knowledge-base associations
        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id,
            ).delete()

        # 5. Add new knowledge-base associations
        for dataset in draft_app_config["datasets"]:
            self.create(AppDatasetJoin, app_id=app_id, dataset_id=dataset["id"])

        # 6. Copy draft config and remove id/version/config_type/updated_at/created_at fields
        draft_app_config_copy = app.draft_app_config.__dict__.copy()
        remove_fields(
            draft_app_config_copy,
            ["id", "version", "config_type", "updated_at", "created_at", "_sa_instance_state"],
        )

        # 7. Get the current max published version
        max_version = self.db.session.query(func.coalesce(func.max(AppConfigVersion.version), 0)).filter(
            AppConfigVersion.app_id == app_id,
            AppConfigVersion.config_type == AppConfigType.PUBLISHED,
        ).scalar()

        # 8. Insert a new published version record
        self.create(
            AppConfigVersion,
            version=max_version + 1,
            config_type=AppConfigType.PUBLISHED,
            **draft_app_config_copy,
        )

        return app

    def cancel_publish_app_config(self, app_id: UUID, account: Account) -> App:
        """Cancel the published config for the specified app"""
        # 1. Get app info and validate permissions
        app = self.get_app(app_id, account)

        # 2. Check whether the app is currently published
        if app.status != AppStatus.PUBLISHED:
            raise FailException("The current application is not published, please verify and try again.")

        # 3. Reset app status to DRAFT and clear runtime config ID
        self.update(app, status=AppStatus.DRAFT, app_config_id=None)

        # 4. Delete the app's associated knowledge-base records
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
        """Get paginated publish history records for a specified app"""
        # 1. Get app info and validate permissions
        self.get_app(app_id, account)

        # 2. Build paginator
        paginator = Paginator(db=self.db, req=req)

        # 3. Execute pagination query
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
        """Rollback a specified historical config version to draft"""
        # 1. Get app info and validate permissions
        app = self.get_app(app_id, account)

        # 2. Query the specified historical config version
        app_config_version = self.get(AppConfigVersion, app_config_version_id)
        if not app_config_version:
            raise NotFoundException("The historical configuration version does not exist, please verify and try again.")

        # 3. Copy the historical config and remove fields that shouldn't be carried over
        draft_app_config_dict = app_config_version.__dict__.copy()
        remove_fields(
            draft_app_config_dict,
            ["id", "app_id", "version", "config_type", "updated_at", "created_at", "_sa_instance_state"],
        )

        # 4. Validate the historical config
        draft_app_config_dict = self._validate_draft_app_config(draft_app_config_dict, account)

        # 5. Update the draft config record
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            # todo: Patch for updating the timestamp
            updated_at=datetime.now(),
            **draft_app_config_dict,
        )

        return draft_app_config_record

    def get_debug_conversation_summary(self, app_id: UUID, account: Account) -> str:
        """Get the long-term memory summary for the debug conversation of a specified app"""
        # 1. Get app info and validate permissions
        app = self.get_app(app_id, account)

        # 2. Get the app draft config and check if long-term memory is enabled
        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("Long-term memory is not enabled for this application, unable to retrieve it.")

        return app.debug_conversation.summary

    def update_debug_conversation_summary(self, app_id: UUID, summary: str, account: Account) -> Conversation:
        """Update the long-term memory summary for a specified app's debug conversation"""
        # 1. Get app info and validate permissions
        app = self.get_app(app_id, account)

        # 2. Get the app draft config and check if long-term memory is enabled
        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("Long-term memory is not enabled for this application, unable to update it.")

        # 3. Update debug conversation summary
        debug_conversation = app.debug_conversation
        self.update(debug_conversation, summary=summary)

        return debug_conversation

    def delete_debug_conversation(self, app_id: UUID, account: Account) -> App:
        """Delete the debug conversation for the specified app"""
        # 1. Get app info and validate permissions
        app = self.get_app(app_id, account)

        # 2. If there is no debug_conversation_id, nothing to do
        if not app.debug_conversation_id:
            return app

        # 3. Reset debug_conversation_id to None
        self.update(app, debug_conversation_id=None)

        return app

    def debug_chat(self, app_id: UUID, query: str, account: Account) -> Generator:
        """Start a debug conversation with the specified app using the given query"""
        # 1. Get app info and validate permissions
        app = self.get_app(app_id, account)

        # 2. Get the latest draft config
        draft_app_config = self.get_draft_app_config(app_id, account)

        # 3. Get the app's debug conversation
        debug_conversation = app.debug_conversation

        # 4. Create a new message record
        message = self.create(
            Message,
            app_id=app_id,
            conversation_id=debug_conversation.id,
            invoke_from=InvokeFrom.DEBUGGER,
            created_by=account.id,
            query=query,
            status=MessageStatus.NORMAL,
        )

        # todo: 5. Instantiate different LLM models based on model_config. Will be extended after multi-LLM support.
        llm = ChatOpenAI(
            model=draft_app_config["model_config"]["model"],
            **draft_app_config["model_config"]["parameters"],
        )

        # 6. Instantiate TokenBufferMemory to extract short-term memory
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=debug_conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=draft_app_config["dialog_round"],
        )

        # 7. Convert tools in draft config to LangChain tools
        tools = self.app_config_service.get_langchain_tools_by_tools_config(draft_app_config["tools"])

        # 8. Check if any datasets are associated
        if draft_app_config["datasets"]:
            # 9. Build a LangChain retrieval tool for the datasets
            dataset_retrieval = self.retrieval_service.create_langchain_tool_from_search(
                flask_app=current_app._get_current_object(),
                dataset_ids=[dataset["id"] for dataset in draft_app_config["datasets"]],
                account_id=account.id,
                retrival_source=RetrievalSource.APP,
                **draft_app_config["retrieval_config"],
            )
            tools.append(dataset_retrieval)

        # todo: 10. Build an Agent, currently using FunctionCallAgent
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
            # 11. Extract thought and answer
            event_id = str(agent_thought.id)

            # 12. Fill agent_thoughts for later persistence
            if agent_thought.event != QueueEvent.PING:
                # 13. For AGENT_MESSAGE events, we accumulate; for others we overwrite
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    if event_id not in agent_thoughts:
                        # 14. Initialize an agent message event
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 15. Accumulate agent message content
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(update={
                            "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                            "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                            "latency": agent_thought.latency,
                        })
                else:
                    # 16. Handle other event types
                    agent_thoughts[event_id] = agent_thought

            data = {
                **agent_thought.model_dump(include={
                    "event", "thought", "observation", "tool", "tool_input", "answer", "latency",
                }),
                "id": event_id,
                "conversation_id": str(debug_conversation.id),
                "message_id": str(message.id),
                "task_id": str(agent_thought.task_id),
            }
            yield f"event: {agent_thought.event}\ndata:{json.dumps(data)}\n\n"

        # 22. Persist the message and reasoning process asynchronously
        thread = Thread(
            target=self.conversation_service.save_agent_thoughts,
            kwargs={
                "flask_app": current_app._get_current_object(),
                "account_id": account.id,
                "app_id": app_id,
                "app_config": draft_app_config,
                "conversation_id": debug_conversation.id,
                "message_id": message.id,
                "agent_thoughts": [agent_thought for agent_thought in agent_thoughts.values()],
            }
        )
        thread.start()

    def stop_debug_chat(self, app_id: UUID, task_id: UUID, account: Account) -> None:
        """Stop a debug chat stream for the specified app + task ID + account"""
        # 1. Get app info and validate permissions
        self.get_app(app_id, account)

        # 2. Use AgentQueueManager to stop the specific task
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.DEBUGGER, account.id)

    def get_debug_conversation_messages_with_page(
            self,
            app_id: UUID,
            req: GetDebugConversationMessagesWithPageReq,
            account: Account
    ) -> tuple[list[Message], Paginator]:
        """Get a paginated list of debug conversation messages for an app"""
        # 1. Get app info and validate permissions
        app = self.get_app(app_id, account)

        # 2. Get the debug conversation of the app
        debug_conversation = app.debug_conversation

        # 3. Build paginator and cursor conditions
        paginator = Paginator(db=self.db, req=req)
        filters = []
        if req.created_at.data:
            # 4. Convert timestamp to datetime
            created_at_datetime = datetime.fromtimestamp(req.created_at.data)
            filters.append(Message.created_at <= created_at_datetime)

        # 5. Execute pagination query
        messages = paginator.paginate(
            self.db.session.query(Message).filter(
                Message.conversation_id == debug_conversation.id,
                Message.status.in_([MessageStatus.STOP, MessageStatus.NORMAL]),
                Message.answer != "",
                *filters,
            ).order_by(desc("created_at"))
        )

        return messages, paginator

    def _validate_draft_app_config(self, draft_app_config: dict[str, Any], account: Account) -> dict[str, Any]:
        """Validate the incoming draft app config and return the validated data"""
        # 1. Validate that the draft config has at least one acceptable field
        acceptable_fields = [
            "model_config", "dialog_round", "preset_prompt",
            "tools", "workflows", "datasets", "retrieval_config",
            "long_term_memory", "opening_statement", "opening_questions",
            "speech_to_text", "text_to_speech", "suggested_after_answer", "review_config",
        ]

        # 2. Check whether provided fields are within acceptable ones
        if (
                not draft_app_config
                or not isinstance(draft_app_config, dict)
                or set(draft_app_config.keys()) - set(acceptable_fields)
        ):
            raise ValidateErrorException("Draft configuration fields are invalid, please verify and try again.")

        # todo: 3. Validate model_config when multiple LLM providers are integrated

        # 4. Validate dialog_round type and range
        if "dialog_round" in draft_app_config:
            dialog_round = draft_app_config["dialog_round"]
            if not isinstance(dialog_round, int) or not (0 <= dialog_round <= 100):
                raise ValidateErrorException("The number of context rounds must be an integer in the range 0–100.")

        # 5. Validate preset_prompt
        if "preset_prompt" in draft_app_config:
            preset_prompt = draft_app_config["preset_prompt"]
            if not isinstance(preset_prompt, str) or len(preset_prompt) > 2000:
                raise ValidateErrorException("Persona and reply logic must be a string with length 0–2000.")

        # 6. Validate tools
        if "tools" in draft_app_config:
            tools = draft_app_config["tools"]
            validate_tools = []

            # 6.1 tools must be a list; an empty list means no tools bound
            if not isinstance(tools, list):
                raise ValidateErrorException("Tool list must be a list.")
            # 6.2 tools length cannot exceed 5
            if len(tools) > 5:
                raise ValidateErrorException("An Agent cannot bind more than 5 tools.")
            # 6.3 Validate each tool in the list
            for tool in tools:
                # 6.4 Tool must be non-empty and of type dict
                if not tool or not isinstance(tool, dict):
                    raise ValidateErrorException("Invalid tool binding parameters.")
                # 6.5 Tool keys must be exactly type/provider_id/tool_id/params
                if set(tool.keys()) != {"type", "provider_id", "tool_id", "params"}:
                    raise ValidateErrorException("Invalid tool binding parameters.")
                # 6.6 type must be either builtin_tool or api_tool
                if tool["type"] not in ["builtin_tool", "api_tool"]:
                    raise ValidateErrorException("Invalid tool binding parameters.")
                # 6.7 Validate provider_id and tool_id
                if (
                        not tool["provider_id"]
                        or not tool["tool_id"]
                        or not isinstance(tool["provider_id"], str)
                        or not isinstance(tool["tool_id"], str)
                ):
                    raise ValidateErrorException("Invalid tool provider or tool identifier.")
                # 6.8 Validate params is a dict
                if not isinstance(tool["params"], dict):
                    raise ValidateErrorException("Tool custom parameters must be in dict format.")
                # 6.9 Check whether the tool actually exists (builtin_tool vs api_tool)
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

            # 6.10 Check duplicate tool bindings
            check_tools = [f"{tool['provider_id']}_{tool['tool_id']}" for tool in validate_tools]
            if len(set(check_tools)) != len(validate_tools):
                raise ValidateErrorException("Duplicate tools detected in tool bindings.")

            # 6.11 Assign validated tools back
            draft_app_config["tools"] = validate_tools

        # todo: 7. Validate workflows after the workflow module is implemented
        if "workflows" in draft_app_config:
            draft_app_config["workflows"] = []

        # 8. Validate datasets (knowledge bases)
        if "datasets" in draft_app_config:
            datasets = draft_app_config["datasets"]

            # 8.1 Datasets must be a list
            if not isinstance(datasets, list):
                raise ValidateErrorException("Dataset binding list has an invalid format.")
            # 8.2 Cannot bind more than 5 datasets
            if len(datasets) > 5:
                raise ValidateErrorException("An Agent cannot bind more than 5 knowledge bases.")
            # 8.3 Validate each dataset ID
            for dataset_id in datasets:
                try:
                    UUID(dataset_id)
                except Exception:
                    raise ValidateErrorException("Knowledge base IDs must be valid UUIDs.")
            # 8.4 Check for duplicate datasets
            if len(set(datasets)) != len(datasets):
                raise ValidateErrorException("Duplicate knowledge bases detected in binding list.")
            # 8.5 Validate dataset permissions, keeping only those belonging to the current account
            dataset_records = self.db.session.query(Dataset).filter(
                Dataset.id.in_(datasets),
                Dataset.account_id == account.id,
            ).all()
            dataset_sets = set([str(dataset_record.id) for dataset_record in dataset_records])
            draft_app_config["datasets"] = [dataset_id for dataset_id in datasets if dataset_id in dataset_sets]

        # 9. Validate retrieval_config
        if "retrieval_config" in draft_app_config:
            retrieval_config = draft_app_config["retrieval_config"]

            # 9.1 retrieval_config must be non-empty and a dict
            if not retrieval_config or not isinstance(retrieval_config, dict):
                raise ValidateErrorException("Retrieval configuration has an invalid format.")
            # 9.2 Validate required fields
            if set(retrieval_config.keys()) != {"retrieval_strategy", "k", "score"}:
                raise ValidateErrorException("Retrieval configuration has an invalid format.")
            # 9.3 Validate retrieval_strategy
            if retrieval_config["retrieval_strategy"] not in ["semantic", "full_text", "hybrid"]:
                raise ValidateErrorException("Retrieval strategy setting is invalid.")
            # 9.4 Validate k (max number of retrieved documents)
            if not isinstance(retrieval_config["k"], int) or not (0 <= retrieval_config["k"] <= 10):
                raise ValidateErrorException(
                    "The maximum number of retrieved documents must be an integer in the range 0–10.")
            # 9.5 Validate score (minimum similarity threshold)
            if not isinstance(retrieval_config["score"], float) or not (0 <= retrieval_config["score"] <= 1):
                raise ValidateErrorException("The minimum similarity score must be a float in the range 0–1.")

        # 10. Validate long_term_memory
        if "long_term_memory" in draft_app_config:
            long_term_memory = draft_app_config["long_term_memory"]

            # 10.1 Check format
            if not long_term_memory or not isinstance(long_term_memory, dict):
                raise ValidateErrorException("Long-term memory configuration has an invalid format.")
            # 10.2 Check attributes
            if (
                    set(long_term_memory.keys()) != {"enable"}
                    or not isinstance(long_term_memory["enable"], bool)
            ):
                raise ValidateErrorException("Long-term memory configuration has an invalid format.")

        # 11. Validate opening_statement
        if "opening_statement" in draft_app_config:
            opening_statement = draft_app_config["opening_statement"]

            # 11.1 Check type and length
            if not isinstance(opening_statement, str) or len(opening_statement) > 2000:
                raise ValidateErrorException("Opening statement length must be between 0 and 2000 characters.")

        # 12. Validate opening_questions
        if "opening_questions" in draft_app_config:
            opening_questions = draft_app_config["opening_questions"]

            # 12.1 Must be a list with length <= 3
            if not isinstance(opening_questions, list) or len(opening_questions) > 3:
                raise ValidateErrorException("Opening questions cannot exceed 3 items.")
            # 12.2 Each opening question must be a string
            for opening_question in opening_questions:
                if not isinstance(opening_question, str):
                    raise ValidateErrorException("Each opening question must be a string.")

        # 13. Validate speech_to_text
        if "speech_to_text" in draft_app_config:
            speech_to_text = draft_app_config["speech_to_text"]

            # 13.1 Check format
            if not speech_to_text or not isinstance(speech_to_text, dict):
                raise ValidateErrorException("Speech-to-text configuration has an invalid format.")
            # 13.2 Check attributes
            if (
                    set(speech_to_text.keys()) != {"enable"}
                    or not isinstance(speech_to_text["enable"], bool)
            ):
                raise ValidateErrorException("Speech-to-text configuration has an invalid format.")

        # 14. Validate text_to_speech
        if "text_to_speech" in draft_app_config:
            text_to_speech = draft_app_config["text_to_speech"]

            # 14.1 Must be a dict
            if not isinstance(text_to_speech, dict):
                raise ValidateErrorException("Text-to-speech configuration has an invalid format.")
            # 14.2 Validate fields
            if (
                    set(text_to_speech.keys()) != {"enable", "voice", "auto_play"}
                    or not isinstance(text_to_speech["enable"], bool)
                    # todo: Add more voices after multimodal Agent support
                    or text_to_speech["voice"] not in ["echo"]
                    or not isinstance(text_to_speech["auto_play"], bool)
            ):
                raise ValidateErrorException("Text-to-speech configuration has an invalid format.")

        # 15. Validate suggested_after_answer
        if "suggested_after_answer" in draft_app_config:
            suggested_after_answer = draft_app_config["suggested_after_answer"]

            # 15.1 Check format
            if not suggested_after_answer or not isinstance(suggested_after_answer, dict):
                raise ValidateErrorException("Suggested-after-answer configuration has an invalid format.")
            # 15.2 Validate fields
            if (
                    set(suggested_after_answer.keys()) != {"enable"}
                    or not isinstance(suggested_after_answer["enable"], bool)
            ):
                raise ValidateErrorException("Suggested-after-answer configuration has an invalid format.")

        # 16. Validate review_config
        if "review_config" in draft_app_config:
            review_config = draft_app_config["review_config"]

            # 16.1 Must be non-empty dict
            if not review_config or not isinstance(review_config, dict):
                raise ValidateErrorException("Review configuration has an invalid format.")
            # 16.2 Validate keys
            if set(review_config.keys()) != {"enable", "keywords", "inputs_config", "outputs_config"}:
                raise ValidateErrorException("Review configuration has an invalid format.")
            # 16.3 Validate enable
            if not isinstance(review_config["enable"], bool):
                raise ValidateErrorException("review.enable has an invalid format.")
            # 16.4 Validate keywords
            if (
                    not isinstance(review_config["keywords"], list)
                    or (review_config["enable"] and len(review_config["keywords"]) == 0)
                    or len(review_config["keywords"]) > 100
            ):
                raise ValidateErrorException(
                    "review.keywords must be non-empty (when enabled) and contain at most 100 keywords.")
            for keyword in review_config["keywords"]:
                if not isinstance(keyword, str):
                    raise ValidateErrorException("Each review.keyword must be a string.")
            # 16.5 Validate inputs_config
            if (
                    not review_config["inputs_config"]
                    or not isinstance(review_config["inputs_config"], dict)
                    or set(review_config["inputs_config"].keys()) != {"enable", "preset_response"}
                    or not isinstance(review_config["inputs_config"]["enable"], bool)
                    or not isinstance(review_config["inputs_config"]["preset_response"], str)
            ):
                raise ValidateErrorException("review.inputs_config must be a dict with valid fields.")
            # 16.6 Validate outputs_config
            if (
                    not review_config["outputs_config"]
                    or not isinstance(review_config["outputs_config"], dict)
                    or set(review_config["outputs_config"].keys()) != {"enable"}
                    or not isinstance(review_config["outputs_config"]["enable"], bool)
            ):
                raise ValidateErrorException("review.outputs_config has an invalid format.")
            # 16.7 When review is enabled, at least one of inputs_config or outputs_config must be enabled
            if review_config["enable"]:
                if (
                        review_config["inputs_config"]["enable"] is False
                        and review_config["outputs_config"]["enable"] is False
                ):
                    raise ValidateErrorException(
                        "At least one of input review or output review must be enabled when review is turned on.")

                if (
                        review_config["inputs_config"]["enable"]
                        and review_config["inputs_config"]["preset_response"].strip() == ""
                ):
                    raise ValidateErrorException(
                        "Preset response for input review cannot be empty when input review is enabled.")

        return draft_app_config
