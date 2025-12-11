#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : app_service.py
"""
import json
import os
from dataclasses import dataclass
from datetime import datetime
from threading import Thread
from typing import Any, Generator
from uuid import UUID

import requests
from flask import current_app
from injector import inject
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel
from langchain_openai import ChatOpenAI
from redis import Redis
from sqlalchemy import func, desc

from internal.core.agent.agents import FunctionCallAgent, AgentQueueManager, ReACTAgent
from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.language_model import LanguageModelManager
from internal.core.memory import TokenBufferMemory
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.entity.ai_entity import OPTIMIZE_PROMPT_TEMPLATE
from internal.entity.app_entity import AppStatus, AppConfigType, DEFAULT_APP_CONFIG
from internal.entity.app_entity import GENERATE_ICON_PROMPT_TEMPLATE
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.entity.dataset_entity import RetrievalSource
from internal.exception import NotFoundException, ForbiddenException, ValidateErrorException, FailException
from internal.lib.helper import remove_fields, get_value_type, generate_random_string
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
    Workflow,
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
from .language_model_service import LanguageModelService
from .retrieval_service import RetrievalService
from ..core.language_model.entities.model_entity import ModelParameterType, ModelFeature
from ..entity.workflow_entity import WorkflowStatus


@inject
@dataclass
class AppService(BaseService):
    """Application service logic."""
    db: SQLAlchemy
    redis_client: Redis
    conversation_service: ConversationService
    retrieval_service: RetrievalService
    app_config_service: AppConfigService
    language_model_service: LanguageModelService
    api_provider_manager: ApiProviderManager
    builtin_provider_manager: BuiltinProviderManager
    language_model_manager: LanguageModelManager

    def auto_create_app(self, name: str, description: str, account_id: UUID) -> None:
        """Automatically create an Agent app using the given name, description, and account ID."""
        # 1. Create an LLM for generating the icon prompt and preset prompt
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.8)

        # 2. Create a DallE API wrapper
        dalle_api_wrapper = DallEAPIWrapper(model="dall-e-3", size="1024x1024")

        # 3. Build the chain for generating the icon
        generate_icon_chain = (
                ChatPromptTemplate.from_template(GENERATE_ICON_PROMPT_TEMPLATE)
                | llm
                | StrOutputParser()
                | dalle_api_wrapper.run
        )

        # 4. Build the chain for generating the preset prompt
        generate_preset_prompt_chain = (
                ChatPromptTemplate.from_messages(
                    [
                        ("system", OPTIMIZE_PROMPT_TEMPLATE),
                        ("human", "App Name: {name}\n\nApp Description: {description}"),
                    ]
                )
                | llm
                | StrOutputParser()
        )

        # 5. Create a parallel chain to execute both chains at the same time
        generate_app_config_chain = RunnableParallel(
            {
                "icon": generate_icon_chain,
                "preset_prompt": generate_preset_prompt_chain,
            }
        )
        app_config = generate_app_config_chain.invoke(
            {"name": name, "description": description}
        )

        # 6. Download the generated image and upload it to Tencent COS
        icon_response = requests.get(app_config.get("icon"))
        if icon_response.status_code == 200:
            icon_content = icon_response.content
        else:
            raise FailException("Error generating app icon image")
        account = self.db.session.query(Account).get(account_id)

        internal_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_dir = os.path.join(internal_path, "storage", "icons")
        os.makedirs(icon_dir, exist_ok=True)
        icon_filename = f"{account_id}_icon.png"
        icon_path = os.path.join(icon_dir, icon_filename)
        with open(icon_path, "wb") as f:
            f.write(icon_content)
        icon = icon_path

        # 7. Open DB auto-commit context
        with self.db.auto_commit():
            # 8. Create app record and flush so we can get the app ID
            app = App(
                account_id=account.id,
                name=name,
                icon=icon,
                description=description,
            )
            self.db.session.add(app)
            self.db.session.flush()

            # 9. Add draft config record
            app_config_version = AppConfigVersion(
                app_id=app.id,
                version=0,
                config_type=AppConfigType.DRAFT,
                **{
                    **DEFAULT_APP_CONFIG,
                    "preset_prompt": app_config.get("preset_prompt", ""),
                },
            )
            self.db.session.add(app_config_version)
            self.db.session.flush()

            # 10. Update the app's draft config ID
            app.draft_app_config_id = app_config_version.id

    def create_app(self, req: CreateAppReq, account: Account) -> App:
        """Create an Agent app."""
        # 1. Open DB auto-commit context
        with self.db.auto_commit():
            # 2. Create app record and flush so we can get the app ID
            app = App(
                account_id=account.id,
                name=req.name.data,
                icon=req.icon.data,
                description=req.description.data,
                status=AppStatus.DRAFT,
            )
            self.db.session.add(app)
            self.db.session.flush()

            # 3. Add draft config record
            app_config_version = AppConfigVersion(
                app_id=app.id,
                version=0,
                config_type=AppConfigType.DRAFT,
                **DEFAULT_APP_CONFIG,
            )
            self.db.session.add(app_config_version)
            self.db.session.flush()

            # 4. Set the app's draft config ID
            app.draft_app_config_id = app_config_version.id

        # 5. Return the created app
        return app

    def get_app(self, app_id: UUID, account: Account) -> App:
        """Get basic app information by app ID."""
        # 1. Query DB for the app
        app = self.get(App, app_id)

        # 2. Check whether the app exists
        if not app:
            raise NotFoundException("The app does not exist. Please check and try again.")

        # 3. Check whether the current account has permission to access this app
        if app.account_id != account.id:
            raise ForbiddenException(
                "The current account has no permission to access this app. Please check and try again."
            )

        return app

    def delete_app(self, app_id: UUID, account: Account) -> App:
        """Delete a specific app by app ID and account. For now we only delete basic app info."""
        app = self.get_app(app_id, account)
        self.delete(app)
        return app

    def update_app(self, app_id: UUID, account: Account, **kwargs) -> App:
        """Update a specific app by app ID, account, and fields."""
        app = self.get_app(app_id, account)
        self.update(app, **kwargs)
        return app

    def copy_app(self, app_id: UUID, account: Account) -> App:
        """Copy the Agent-related configuration from the given app and create a new Agent."""
        # 1. Get the app and its draft config, and check permissions
        app = self.get_app(app_id, account)
        draft_app_config = app.draft_app_config

        # 2. Convert data to dict and remove unwanted fields
        app_dict = app.__dict__.copy()
        draft_app_config_dict = draft_app_config.__dict__.copy()

        # 3. Remove fields that should not be copied
        app_remove_fields = [
            "id",
            "app_config_id",
            "draft_app_config_id",
            "debug_conversation_id",
            "status",
            "updated_at",
            "created_at",
            "_sa_instance_state",
        ]
        draft_app_config_remove_fields = [
            "id",
            "app_id",
            "version",
            "updated_at",
            "created_at",
            "_sa_instance_state",
        ]
        remove_fields(app_dict, app_remove_fields)
        remove_fields(draft_app_config_dict, draft_app_config_remove_fields)

        # 4. Open DB auto-commit context
        with self.db.auto_commit():
            # 5. Create a new app record
            new_app = App(**app_dict, status=AppStatus.DRAFT)
            self.db.session.add(new_app)
            self.db.session.flush()

            # 6. Add draft config for the new app
            new_draft_app_config = AppConfigVersion(
                **draft_app_config_dict,
                app_id=new_app.id,
                version=0,
            )
            self.db.session.add(new_draft_app_config)
            self.db.session.flush()

            # 7. Update the new app's draft config ID
            new_app.draft_app_config_id = new_draft_app_config.id

        # 8. Return the newly created app
        return new_app

    def get_apps_with_page(self, req: GetAppsWithPageReq, account: Account) -> tuple[list[App], Paginator]:
        """Get a paginated list of apps for the current account."""
        # 1. Build paginator
        paginator = Paginator(db=self.db, req=req)

        # 2. Build filter conditions
        filters = [App.account_id == account.id]
        if req.search_word.data:
            filters.append(App.name.ilike(f"%{req.search_word.data}%"))

        # 3. Execute pagination
        apps = paginator.paginate(
            self.db.session.query(App).filter(*filters).order_by(desc("created_at"))
        )

        return apps, paginator

    def get_draft_app_config(self, app_id: UUID, account: Account) -> dict[str, Any]:
        """Get the draft configuration for the specified app ID."""
        app = self.get_app(app_id, account)
        return self.app_config_service.get_draft_app_config(app)

    def update_draft_app_config(
            self,
            app_id: UUID,
            draft_app_config: dict[str, Any],
            account: Account,
    ) -> AppConfigVersion:
        """Update the latest draft configuration for the specified app."""
        # 1. Get app info and check permissions
        app = self.get_app(app_id, account)

        # 2. Validate the submitted draft configuration
        draft_app_config = self._validate_draft_app_config(draft_app_config, account)

        # 3. Get the existing latest draft configuration for the app
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            # todo: Because we use server_onupdate, we need to pass updated_at manually for now
            updated_at=datetime.now(),
            **draft_app_config,
        )

        return draft_app_config_record

    def publish_draft_app_config(self, app_id: UUID, account: Account) -> App:
        """Publish/update the draft configuration of an app as the runtime configuration."""
        # 1. Get app info and draft configuration
        app = self.get_app(app_id, account)
        draft_app_config = self.get_draft_app_config(app_id, account)

        # 2. Create runtime configuration (we do not delete historical runtime configs here)
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
            workflows=[workflow["id"] for workflow in draft_app_config["workflows"]],
            retrieval_config=draft_app_config["retrieval_config"],
            long_term_memory=draft_app_config["long_term_memory"],
            opening_statement=draft_app_config["opening_statement"],
            opening_questions=draft_app_config["opening_questions"],
            speech_to_text=draft_app_config["speech_to_text"],
            text_to_speech=draft_app_config["text_to_speech"],
            suggested_after_answer=draft_app_config["suggested_after_answer"],
            review_config=draft_app_config["review_config"],
        )

        # 3. Update the app's runtime config ID and status
        self.update(app, app_config_id=app_config.id, status=AppStatus.PUBLISHED)

        # 4. Delete existing dataset association records
        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id,
            ).delete()

        # 5. Add new dataset association records
        for dataset in draft_app_config["datasets"]:
            self.create(AppDatasetJoin, app_id=app_id, dataset_id=dataset["id"])

        # 6. Copy the app draft configuration and remove fields: id, version, config_type, updated_at, created_at
        draft_app_config_copy = app.draft_app_config.__dict__.copy()
        remove_fields(
            draft_app_config_copy,
            [
                "id",
                "version",
                "config_type",
                "updated_at",
                "created_at",
                "_sa_instance_state",
            ],
        )

        # 7. Get the current maximum published version
        max_version = (
            self.db.session.query(
                func.coalesce(func.max(AppConfigVersion.version), 0)
            )
            .filter(
                AppConfigVersion.app_id == app_id,
                AppConfigVersion.config_type == AppConfigType.PUBLISHED,
            )
            .scalar()
        )

        # 8. Insert a new published history configuration
        self.create(
            AppConfigVersion,
            version=max_version + 1,
            config_type=AppConfigType.PUBLISHED,
            **draft_app_config_copy,
        )

        return app

    def cancel_publish_app_config(self, app_id: UUID, account: Account) -> App:
        """Unpublish the runtime configuration for the specified app."""
        # 1. Get app info and check permissions
        app = self.get_app(app_id, account)

        # 2. Check whether the app is currently published
        if app.status != AppStatus.PUBLISHED:
            raise FailException("The app is not published. Please check and try again.")

        # 3. Change status to DRAFT and clear the runtime config ID
        self.update(app, status=AppStatus.DRAFT, app_config_id=None)

        # 4. Delete app–dataset association records
        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id,
            ).delete()

        return app

    def get_publish_histories_with_page(
            self,
            app_id: UUID,
            req: GetPublishHistoriesWithPageReq,
            account: Account,
    ) -> tuple[list[AppConfigVersion], Paginator]:
        """Get a paginated list of published history configurations for the given app."""
        # 1. Get app info and check permissions
        self.get_app(app_id, account)

        # 2. Build paginator
        paginator = Paginator(db=self.db, req=req)

        # 3. Execute pagination and get data
        app_config_versions = paginator.paginate(
            self.db.session.query(AppConfigVersion)
            .filter(
                AppConfigVersion.app_id == app_id,
                AppConfigVersion.config_type == AppConfigType.PUBLISHED,
            )
            .order_by(desc("version"))
        )

        return app_config_versions, paginator

    def fallback_history_to_draft(
            self,
            app_id: UUID,
            app_config_version_id: UUID,
            account: Account,
    ) -> AppConfigVersion:
        """Revert a specific published configuration to the current draft."""
        # 1. Get app info and check permissions
        app = self.get_app(app_id, account)

        # 2. Get the specified historical config version
        app_config_version = self.get(AppConfigVersion, app_config_version_id)
        if not app_config_version:
            raise NotFoundException(
                "The historical configuration version does not exist. Please check and try again."
            )

        # 3. Clean up historical config (remove deleted tools, datasets, workflows)
        draft_app_config_dict = app_config_version.__dict__.copy()
        remove_fields(
            draft_app_config_dict,
            [
                "id",
                "app_id",
                "version",
                "config_type",
                "updated_at",
                "created_at",
                "_sa_instance_state",
            ],
        )

        # 4. Validate the historical configuration
        draft_app_config_dict = self._validate_draft_app_config(
            draft_app_config_dict, account
        )

        # 5. Update the draft configuration
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            # todo: patch for updated_at
            updated_at=datetime.now(),
            **draft_app_config_dict,
        )

        return draft_app_config_record

    def get_debug_conversation_summary(self, app_id: UUID, account: Account) -> str:
        """Get the debug conversation long-term memory for the specified app."""
        # 1. Get app info and check permissions
        app = self.get_app(app_id, account)

        # 2. Get draft configuration and verify long-term memory is enabled
        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException(
                "Long-term memory is not enabled for this app and cannot be retrieved."
            )

        return app.debug_conversation.summary

    def update_debug_conversation_summary(
            self, app_id: UUID, summary: str, account: Account
    ) -> Conversation:
        """Update the debug conversation long-term memory summary for the specified app."""
        # 1. Get app info and check permissions
        app = self.get_app(app_id, account)

        # 2. Get draft configuration and verify long-term memory is enabled
        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException(
                "Long-term memory is not enabled for this app and cannot be updated."
            )

        # 3. Update long-term memory summary
        debug_conversation = app.debug_conversation
        self.update(debug_conversation, summary=summary)

        return debug_conversation

    def delete_debug_conversation(self, app_id: UUID, account: Account) -> App:
        """Delete the debug conversation for the specified app."""
        # 1. Get app info and check permissions
        app = self.get_app(app_id, account)

        # 2. If debug_conversation_id is empty, there is nothing to delete
        if not app.debug_conversation_id:
            return app

        # 3. Otherwise reset debug_conversation_id to None
        self.update(app, debug_conversation_id=None)

        return app

    def debug_chat(self, app_id: UUID, query: str, account: Account) -> Generator:
        """Start a debug conversation with an app using the given query."""
        # 1. Get app info and check permissions
        app = self.get_app(app_id, account)

        # 2. Get the latest draft configuration for the app
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

        # 5. Load the LLM from the language model manager
        llm = self.language_model_service.load_language_model(
            draft_app_config.get("model_config", {})
        )

        # 6. Initialize TokenBufferMemory for short-term memory
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=debug_conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=draft_app_config["dialog_round"],
        )

        # 7. Convert tools in the draft config into LangChain tools
        tools = self.app_config_service.get_langchain_tools_by_tools_config(
            draft_app_config["tools"]
        )

        # 8. Check whether any datasets are bound
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

        # 10. Check whether workflows are bound; if so, convert them to tools and add to tools list
        if draft_app_config["workflows"]:
            workflow_tools = self.app_config_service.get_langchain_tools_by_workflow_ids(
                [workflow["id"] for workflow in draft_app_config["workflows"]]
            )
            tools.extend(workflow_tools)

        # 11. Choose the Agent type based on whether the LLM supports tool_call
        agent_class = (
            FunctionCallAgent
            if ModelFeature.TOOL_CALL in llm.features
            else ReACTAgent
        )
        agent = agent_class(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.DEBUGGER,
                preset_prompt=draft_app_config["preset_prompt"],
                enable_long_term_memory=draft_app_config["long_term_memory"]["enable"],
                tools=tools,
                review_config=draft_app_config["review_config"],
            ),
        )

        agent_thoughts: dict[str, Any] = {}
        for agent_thought in agent.stream(
                {
                    "messages": [HumanMessage(query)],
                    "history": history,
                    "long_term_memory": debug_conversation.summary,
                }
        ):
            # 12. Extract thought and answer
            event_id = str(agent_thought.id)

            # 13. Fill data into agent_thoughts for later persistence
            if agent_thought.event != QueueEvent.PING:
                # 14. For AGENT_MESSAGE, append content; for others, overwrite
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    if event_id not in agent_thoughts:
                        # 15. Initialize agent message event
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 16. Append to existing agent message
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(
                            update={
                                "thought": agent_thoughts[event_id].thought
                                           + agent_thought.thought,
                                # Message-related fields
                                "message": agent_thought.message,
                                "message_token_count": agent_thought.message_token_count,
                                "message_unit_price": agent_thought.message_unit_price,
                                "message_price_unit": agent_thought.message_price_unit,
                                # Answer-related fields
                                "answer": agent_thoughts[event_id].answer
                                          + agent_thought.answer,
                                "answer_token_count": agent_thought.answer_token_count,
                                "answer_unit_price": agent_thought.answer_unit_price,
                                "answer_price_unit": agent_thought.answer_price_unit,
                                # Agent reasoning statistics
                                "total_token_count": agent_thought.total_token_count,
                                "total_price": agent_thought.total_price,
                                "latency": agent_thought.latency,
                            }
                        )
                else:
                    # 17. Handle other event types
                    agent_thoughts[event_id] = agent_thought

            data = {
                **agent_thought.model_dump(
                    include={
                        "event",
                        "thought",
                        "observation",
                        "tool",
                        "tool_input",
                        "answer",
                        "total_token_count",
                        "total_price",
                        "latency",
                    }
                ),
                "id": event_id,
                "conversation_id": str(debug_conversation.id),
                "message_id": str(message.id),
                "task_id": str(agent_thought.task_id),
            }
            yield f"event: {agent_thought.event}\ndata:{json.dumps(data)}\n\n"

        # 18. Persist the message and reasoning process to the database in a background thread
        thread = Thread(
            target=self.conversation_service.save_agent_thoughts,
            kwargs={
                "flask_app": current_app._get_current_object(),
                "account_id": account.id,
                "app_id": app_id,
                "app_config": draft_app_config,
                "conversation_id": debug_conversation.id,
                "message_id": message.id,
                "agent_thoughts": [
                    agent_thought for agent_thought in agent_thoughts.values()
                ],
            },
        )
        thread.start()

    def stop_debug_chat(self, app_id: UUID, task_id: UUID, account: Account) -> None:
        """Stop a debug session (interrupt streaming events) for the specified app and task ID."""
        # 1. Get app info and check permissions
        self.get_app(app_id, account)

        # 2. Use the AgentQueueManager to stop the specific task
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.DEBUGGER, account.id)

    def get_debug_conversation_messages_with_page(
            self,
            app_id: UUID,
            req: GetDebugConversationMessagesWithPageReq,
            account: Account,
    ) -> tuple[list[Message], Paginator]:
        """Get a paginated list of debug conversation messages for the specified app."""
        # 1. Get app info and check permissions
        app = self.get_app(app_id, account)

        # 2. Get the app's debug conversation
        debug_conversation = app.debug_conversation

        # 3. Build paginator and cursor conditions
        paginator = Paginator(db=self.db, req=req)
        filters = []
        if req.created_at.data:
            # 4. Convert timestamp to datetime
            created_at_datetime = datetime.fromtimestamp(req.created_at.data)
            filters.append(Message.created_at <= created_at_datetime)

        # 5. Execute pagination and query data
        messages = paginator.paginate(
            self.db.session.query(Message).filter(
                Message.conversation_id == debug_conversation.id,
                Message.status.in_([MessageStatus.STOP, MessageStatus.NORMAL]),
                Message.answer != "",
                *filters,
            ).order_by(desc("created_at"))
        )

        return messages, paginator

    def get_published_config(self, app_id: UUID, account: Account) -> dict[str, Any]:
        """Get the published configuration (e.g. WebApp token/status) for the specified app."""
        # 1. Get app info and check permissions
        app = self.get_app(app_id, account)

        # 2. Build and return the published config
        return {
            "web_app": {
                "token": app.token_with_default,
                "status": app.status,
            }
        }

    def regenerate_web_app_token(self, app_id: UUID, account: Account) -> str:
        """Regenerate the WebApp token for the specified app."""
        # 1. Get app info and check permissions
        app = self.get_app(app_id, account)

        # 2. Check whether the app is published
        if app.status != AppStatus.PUBLISHED:
            raise FailException(
                "The app is not published and cannot generate a WebApp token."
            )

        # 3. Regenerate token and update the app
        token = generate_random_string(16)
        self.update(app, token=token)

        return token

    def _validate_draft_app_config(
            self, draft_app_config: dict[str, Any], account: Account
    ) -> dict[str, Any]:
        """Validate the submitted draft configuration and return the validated data."""
        # 1. Required fields: draft config must contain at least one valid updatable field
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
            "suggested_after_answer",
            "review_config",
        ]

        # 2. Check whether the submitted draft config is valid and only contains acceptable fields
        if (
                not draft_app_config
                or not isinstance(draft_app_config, dict)
                or set(draft_app_config.keys()) - set(acceptable_fields)
        ):
            raise ValidateErrorException(
                "Draft configuration fields are invalid. Please check and try again."
            )

        # 3. Validate model_config: provider/model are strictly validated (errors raise),
        #    parameters are leniently validated (fallback to defaults on error).
        if "model_config" in draft_app_config:
            # 3.1 Get model configuration and ensure it is a dict
            model_config = draft_app_config["model_config"]
            if not isinstance(model_config, dict):
                raise ValidateErrorException(
                    "Model configuration format error. Please check and try again."
                )

            # 3.2 Validate model_config keys
            if set(model_config.keys()) != {"provider", "model", "parameters"}:
                raise ValidateErrorException(
                    "Model configuration keys are invalid. Please check and try again."
                )

            # 3.3 Validate provider information
            if not model_config["provider"] or not isinstance(
                    model_config["provider"], str
            ):
                raise ValidateErrorException(
                    "Model provider type must be a string."
                )
            provider = self.language_model_manager.get_provider(
                model_config["provider"]
            )
            if not provider:
                raise ValidateErrorException(
                    "The specified model provider does not exist. Please check and try again."
                )

            # 3.4 Validate model information
            if not model_config["model"] or not isinstance(
                    model_config["model"], str
            ):
                raise ValidateErrorException(
                    "Model name must be a string."
                )
            model_entity = provider.get_model_entity(model_config["model"])
            if not model_entity:
                raise ValidateErrorException(
                    "The specified model does not exist under this provider. Please check and try again."
                )

            # 3.5 Validate parameters; if invalid, use defaults and remove extra fields
            parameters: dict[str, Any] = {}
            for parameter in model_entity.parameters:
                # 3.6 Get parameter value from model_config or use default
                parameter_value = model_config["parameters"].get(
                    parameter.name, parameter.default
                )

                # 3.7 Check whether parameter is required
                if parameter.required:
                    # 3.8 Required parameter must not be None; if None, use default
                    if parameter_value is None:
                        parameter_value = parameter.default
                    else:
                        # 3.9 For non-empty values, validate type; if invalid, use default
                        if get_value_type(parameter_value) != parameter.type.value:
                            parameter_value = parameter.default
                else:
                    # 3.10 For optional parameters, validate type only when non-empty
                    if parameter_value is not None:
                        if get_value_type(parameter_value) != parameter.type.value:
                            parameter_value = parameter.default

                # 3.11 If the parameter has options, its value must be one of them
                if parameter.options and parameter_value not in parameter.options:
                    parameter_value = parameter.default

                # 3.12 For int/float parameters, validate min/max if present
                if (
                        parameter.type
                        in [ModelParameterType.INT, ModelParameterType.FLOAT]
                        and parameter_value is not None
                ):
                    # 3.13 Validate min/max
                    if (
                            (parameter.min and parameter_value < parameter.min)
                            or (parameter.max and parameter_value > parameter.max)
                    ):
                        parameter_value = parameter.default

                parameters[parameter.name] = parameter_value

            # 3.14 Overwrite model_config in the Agent draft with validated parameters
            model_config["parameters"] = parameters
            draft_app_config["model_config"] = model_config

        # 4. Validate dialog_round: type and range
        if "dialog_round" in draft_app_config:
            dialog_round = draft_app_config["dialog_round"]
            if not isinstance(dialog_round, int) or not (0 <= dialog_round <= 100):
                raise ValidateErrorException(
                    "Dialog round (context turns) must be an integer in the range 0–100."
                )

        # 5. Validate preset_prompt
        if "preset_prompt" in draft_app_config:
            preset_prompt = draft_app_config["preset_prompt"]
            if not isinstance(preset_prompt, str) or len(preset_prompt) > 2000:
                raise ValidateErrorException(
                    "Persona and reply logic must be a string with length between 0 and 2000 characters."
                )

        # 6. Validate tools
        if "tools" in draft_app_config:
            tools = draft_app_config["tools"]
            validate_tools: list[dict] = []

            # 6.1 tools must be a list; an empty list means no tools are bound
            if not isinstance(tools, list):
                raise ValidateErrorException("Tools must be provided as a list.")
            # 6.2 At most 5 tools can be bound
            if len(tools) > 5:
                raise ValidateErrorException(
                    "An Agent cannot bind more than 5 tools."
                )
            # 6.3 Validate each tool in the list
            for tool in tools:
                # 6.4 Tool must be non-empty and must be a dict
                if not tool or not isinstance(tool, dict):
                    raise ValidateErrorException(
                        "Tool binding parameters are invalid."
                    )
                # 6.5 Tool keys must be type, provider_id, tool_id, params
                if set(tool.keys()) != {"type", "provider_id", "tool_id", "params"}:
                    raise ValidateErrorException(
                        "Tool binding parameters are invalid."
                    )
                # 6.6 type must be one of builtin_tool or api_tool
                if tool["type"] not in ["builtin_tool", "api_tool"]:
                    raise ValidateErrorException(
                        "Tool binding parameters are invalid."
                    )
                # 6.7 Validate provider_id and tool_id
                if (
                        not tool["provider_id"]
                        or not tool["tool_id"]
                        or not isinstance(tool["provider_id"], str)
                        or not isinstance(tool["tool_id"], str)
                ):
                    raise ValidateErrorException(
                        "Tool provider or tool identifier parameters are invalid."
                    )
                # 6.8 Validate params: must be a dict
                if not isinstance(tool["params"], dict):
                    raise ValidateErrorException(
                        "Custom tool parameter format is invalid."
                    )
                # 6.9 Validate that the tool exists; split into builtin_tool and api_tool
                if tool["type"] == "builtin_tool":
                    builtin_tool = self.builtin_provider_manager.get_tool(
                        tool["provider_id"], tool["tool_id"]
                    )
                    if not builtin_tool:
                        continue
                else:
                    api_tool = (
                        self.db.session.query(ApiTool)
                        .filter(
                            ApiTool.provider_id == tool["provider_id"],
                            ApiTool.name == tool["tool_id"],
                            ApiTool.account_id == account.id,
                        )
                        .one_or_none()
                    )
                    if not api_tool:
                        continue

                validate_tools.append(tool)

            # 6.10 Check for duplicate tool bindings
            check_tools = [
                f"{tool['provider_id']}_{tool['tool_id']}"
                for tool in validate_tools
            ]
            if len(set(check_tools)) != len(validate_tools):
                raise ValidateErrorException("Duplicate tools are bound.")

            # 6.11 Overwrite tools with validated list
            draft_app_config["tools"] = validate_tools

        # 7. Validate workflows: keep only published workflows with correct permissions
        #    (we do not check whether workflows can run successfully during config update).
        if "workflows" in draft_app_config:
            workflows = draft_app_config["workflows"]

            # 7.1 workflows must be a list
            if not isinstance(workflows, list):
                raise ValidateErrorException(
                    "Workflow binding list parameter format is invalid."
                )
            # 7.2 At most 5 workflows can be bound
            if len(workflows) > 5:
                raise ValidateErrorException(
                    "An Agent cannot bind more than 5 workflows."
                )
            # 7.3 Validate each workflow ID; must be a UUID
            for workflow_id in workflows:
                try:
                    UUID(workflow_id)
                except Exception:
                    raise ValidateErrorException(
                        "Workflow ID must be a valid UUID."
                    )
            # 7.4 Check for duplicate workflow bindings
            if len(set(workflows)) != len(workflows):
                raise ValidateErrorException("Duplicate workflows are bound.")
            # 7.5 Validate workflow permissions: keep only workflows owned by this account and already published
            workflow_records = self.db.session.query(Workflow).filter(
                Workflow.id.in_(workflows),
                Workflow.account_id == account.id,
                Workflow.status == WorkflowStatus.PUBLISHED,
            ).all()
            workflow_sets = {str(workflow_record.id) for workflow_record in workflow_records}
            draft_app_config["workflows"] = [
                workflow_id for workflow_id in workflows if workflow_id in workflow_sets
            ]

        # 8. Validate datasets (knowledge base) list
        if "datasets" in draft_app_config:
            datasets = draft_app_config["datasets"]

            # 8.1 datasets must be a list
            if not isinstance(datasets, list):
                raise ValidateErrorException(
                    "Dataset binding list parameter format is invalid."
                )
            # 8.2 At most 5 datasets can be bound
            if len(datasets) > 5:
                raise ValidateErrorException(
                    "An Agent cannot bind more than 5 datasets."
                )
            # 8.3 Validate each dataset ID; must be a UUID
            for dataset_id in datasets:
                try:
                    UUID(dataset_id)
                except Exception:
                    raise ValidateErrorException(
                        "Dataset list parameters must be valid UUIDs."
                    )
            # 8.4 Check for duplicate datasets
            if len(set(datasets)) != len(datasets):
                raise ValidateErrorException("Duplicate datasets are bound.")
            # 8.5 Validate dataset permissions: keep only datasets owned by the current account
            dataset_records = self.db.session.query(Dataset).filter(
                Dataset.id.in_(datasets),
                Dataset.account_id == account.id,
            ).all()
            dataset_sets = {str(dataset_record.id) for dataset_record in dataset_records}
            draft_app_config["datasets"] = [
                dataset_id for dataset_id in datasets if dataset_id in dataset_sets
            ]

        # 9. Validate retrieval_config
        if "retrieval_config" in draft_app_config:
            retrieval_config = draft_app_config["retrieval_config"]

            # 9.1 retrieval_config must be non-empty and a dict
            if not retrieval_config or not isinstance(retrieval_config, dict):
                raise ValidateErrorException("Retrieval configuration format is invalid.")
            # 9.2 Validate retrieval_config keys
            if set(retrieval_config.keys()) != {"retrieval_strategy", "k", "score"}:
                raise ValidateErrorException("Retrieval configuration format is invalid.")
            # 9.3 Validate retrieval_strategy
            if retrieval_config["retrieval_strategy"] not in [
                "semantic",
                "full_text",
                "hybrid",
            ]:
                raise ValidateErrorException("Retrieval strategy format is invalid.")
            # 9.4 Validate maximum number of results k
            if not isinstance(retrieval_config["k"], int) or not (
                    0 <= retrieval_config["k"] <= 10
            ):
                raise ValidateErrorException(
                    "Maximum number of retrieved items must be in the range 0–10."
                )
            # 9.5 Validate score / minimum similarity
            if not isinstance(retrieval_config["score"], float) or not (
                    0 <= retrieval_config["score"] <= 1
            ):
                raise ValidateErrorException(
                    "Minimum similarity score must be in the range 0–1."
                )

        # 10. Validate long_term_memory configuration
        if "long_term_memory" in draft_app_config:
            long_term_memory = draft_app_config["long_term_memory"]

            # 10.1 Must be a non-empty dict
            if not long_term_memory or not isinstance(long_term_memory, dict):
                raise ValidateErrorException("Long-term memory configuration is invalid.")
            # 10.2 Must contain enable and enable must be a bool
            if (
                    set(long_term_memory.keys()) != {"enable"}
                    or not isinstance(long_term_memory["enable"], bool)
            ):
                raise ValidateErrorException("Long-term memory configuration is invalid.")

        # 11. Validate opening_statement
        if "opening_statement" in draft_app_config:
            opening_statement = draft_app_config["opening_statement"]

            # 11.1 Must be a string of length 0–2000
            if not isinstance(opening_statement, str) or len(opening_statement) > 2000:
                raise ValidateErrorException(
                    "Opening statement length must be in the range 0–2000."
                )

        # 12. Validate opening_questions
        if "opening_questions" in draft_app_config:
            opening_questions = draft_app_config["opening_questions"]

            # 12.1 Must be a list with at most 3 items
            if not isinstance(opening_questions, list) or len(opening_questions) > 3:
                raise ValidateErrorException(
                    "Opening questions cannot exceed 3 items."
                )
            # 12.2 Each item must be a string
            for opening_question in opening_questions:
                if not isinstance(opening_question, str):
                    raise ValidateErrorException(
                        "Each opening question must be a string."
                    )

        # 13. Validate speech_to_text configuration
        if "speech_to_text" in draft_app_config:
            speech_to_text = draft_app_config["speech_to_text"]

            # 13.1 Must be a non-empty dict
            if not speech_to_text or not isinstance(speech_to_text, dict):
                raise ValidateErrorException("Speech-to-text configuration is invalid.")
            # 13.2 Must contain enable and enable must be a bool
            if (
                    set(speech_to_text.keys()) != {"enable"}
                    or not isinstance(speech_to_text["enable"], bool)
            ):
                raise ValidateErrorException("Speech-to-text configuration is invalid.")

        # 14. Validate text_to_speech configuration
        if "text_to_speech" in draft_app_config:
            text_to_speech = draft_app_config["text_to_speech"]

            # 14.1 Must be a dict
            if not isinstance(text_to_speech, dict):
                raise ValidateErrorException("Text-to-speech configuration is invalid.")
            # 14.2 Validate fields and types
            if (
                    set(text_to_speech.keys()) != {"enable", "voice", "auto_play"}
                    or not isinstance(text_to_speech["enable"], bool)
                    # todo: Add more voices when multimodal Agent is implemented
                    or text_to_speech["voice"] not in ["echo"]
                    or not isinstance(text_to_speech["auto_play"], bool)
            ):
                raise ValidateErrorException("Text-to-speech configuration is invalid.")

        # 15. Validate suggested_after_answer configuration
        if "suggested_after_answer" in draft_app_config:
            suggested_after_answer = draft_app_config["suggested_after_answer"]

            # 15.1 Must be a non-empty dict
            if not suggested_after_answer or not isinstance(
                    suggested_after_answer, dict
            ):
                raise ValidateErrorException(
                    "Suggested-questions-after-answer configuration is invalid."
                )
            # 15.2 Must contain enable and enable must be a bool
            if (
                    set(suggested_after_answer.keys()) != {"enable"}
                    or not isinstance(suggested_after_answer["enable"], bool)
            ):
                raise ValidateErrorException(
                    "Suggested-questions-after-answer configuration is invalid."
                )

        # 16. Validate review_config (content moderation / review configuration)
        if "review_config" in draft_app_config:
            review_config = draft_app_config["review_config"]

            # 16.1 Must be a non-empty dict
            if not review_config or not isinstance(review_config, dict):
                raise ValidateErrorException("Review configuration is invalid.")
            # 16.2 Must contain the correct keys
            if set(review_config.keys()) != {
                "enable",
                "keywords",
                "inputs_config",
                "outputs_config",
            }:
                raise ValidateErrorException("Review configuration is invalid.")
            # 16.3 Validate enable
            if not isinstance(review_config["enable"], bool):
                raise ValidateErrorException("review.enable must be a boolean.")
            # 16.4 Validate keywords
            if (
                    not isinstance(review_config["keywords"], list)
                    or (review_config["enable"] and len(review_config["keywords"]) == 0)
                    or len(review_config["keywords"]) > 100
            ):
                raise ValidateErrorException(
                    "review.keywords must be non-empty when review is enabled and cannot exceed 100 keywords."
                )
            for keyword in review_config["keywords"]:
                if not isinstance(keyword, str):
                    raise ValidateErrorException(
                        "review.keywords items must be strings."
                    )
            # 16.5 Validate inputs_config
            if (
                    not review_config["inputs_config"]
                    or not isinstance(review_config["inputs_config"], dict)
                    or set(review_config["inputs_config"].keys())
                    != {"enable", "preset_response"}
                    or not isinstance(review_config["inputs_config"]["enable"], bool)
                    or not isinstance(
                review_config["inputs_config"]["preset_response"], str
            )
            ):
                raise ValidateErrorException(
                    "review.inputs_config must be a valid dictionary."
                )
            # 16.6 Validate outputs_config
            if (
                    not review_config["outputs_config"]
                    or not isinstance(review_config["outputs_config"], dict)
                    or set(review_config["outputs_config"].keys()) != {"enable"}
                    or not isinstance(review_config["outputs_config"]["enable"], bool)
            ):
                raise ValidateErrorException(
                    "review.outputs_config must be a valid dictionary."
                )
            # 16.7 If review is enabled, at least one of input or output checks must be enabled
            if review_config["enable"]:
                if (
                        review_config["inputs_config"]["enable"] is False
                        and review_config["outputs_config"]["enable"] is False
                ):
                    raise ValidateErrorException(
                        "When review is enabled, at least one of input or output review must be turned on."
                    )

                if (
                        review_config["inputs_config"]["enable"]
                        and review_config["inputs_config"]["preset_response"].strip() == ""
                ):
                    raise ValidateErrorException(
                        "Preset response for input review cannot be empty."
                    )

        return draft_app_config
