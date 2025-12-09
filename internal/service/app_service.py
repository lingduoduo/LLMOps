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
from internal.lib.helper import remove_fields, get_value_type
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
from .language_model_service import LanguageModelService
from .retrieval_service import RetrievalService
from ..core.language_model.entities.model_entity import ModelParameterType, ModelFeature


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
        """Automatically create an Agent application using AI from app name, description, and account ID."""
        # 1. Create an LLM for generating icon prompt and preset prompt
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.8)

        # 2. Create a DALL·E API wrapper
        dalle_api_wrapper = DallEAPIWrapper(model="dall-e-3", size="1024x1024")

        # 3. Build chain for generating icon
        generate_icon_chain = ChatPromptTemplate.from_template(
            GENERATE_ICON_PROMPT_TEMPLATE
        ) | llm | StrOutputParser() | dalle_api_wrapper.run

        # 4. Build chain for generating preset prompt
        generate_preset_prompt_chain = ChatPromptTemplate.from_messages([
            ("system", OPTIMIZE_PROMPT_TEMPLATE),
            ("human", "App Name: {name}\n\nApp Description: {description}")
        ]) | llm | StrOutputParser()

        # 5. Build parallel chain to execute both chains simultaneously
        generate_app_config_chain = RunnableParallel({
            "icon": generate_icon_chain,
            "preset_prompt": generate_preset_prompt_chain,
        })
        app_config = generate_app_config_chain.invoke({"name": name, "description": description})

        # 6. Download image locally and then upload to COS
        icon_response = requests.get(app_config.get("icon"))
        if icon_response.status_code == 200:
            icon_content = icon_response.content
        else:
            raise FailException("Error generating application icon image.")
        account = self.db.session.query(Account).get(account_id)

        internal_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_dir = os.path.join(internal_path, "storage", "icons")
        os.makedirs(icon_dir, exist_ok=True)
        icon_filename = f"{account_id}_icon.png"
        icon_path = os.path.join(icon_dir, icon_filename)
        with open(icon_path, "wb") as f:
            f.write(icon_content)
        icon = icon_path

        # 7. Start DB auto-commit context
        with self.db.auto_commit():
            # 8. Create app record and flush to obtain app ID
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
                }
            )
            self.db.session.add(app_config_version)
            self.db.session.flush()

            # 10. Update app draft_config_id
            app.draft_app_config_id = app_config_version.id

    def create_app(self, req: CreateAppReq, account: Account) -> App:
        """Create an Agent application."""
        # 1. Start DB auto-commit context
        with self.db.auto_commit():
            # 2. Create app record and flush to obtain app ID
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

            # 4. Bind draft config ID to the app
            app.draft_app_config_id = app_config_version.id

        # 5. Return created app record
        return app

    def get_app(self, app_id: UUID, account: Account) -> App:
        """Get basic app information by ID."""
        # 1. Query DB for app
        app = self.get(App, app_id)

        # 2. Ensure app exists
        if not app:
            raise NotFoundException("The application does not exist. Please check and try again.")

        # 3. Check whether the current account has access to this app
        if app.account_id != account.id:
            raise ForbiddenException("You do not have permission to access this application.")

        return app

    def delete_app(self, app_id: UUID, account: Account) -> App:
        """Delete an application by ID and account; currently only deletes app base info."""
        app = self.get_app(app_id, account)
        self.delete(app)
        return app

    def update_app(self, app_id: UUID, account: Account, **kwargs) -> App:
        """Update an application by ID and account with the provided fields."""
        app = self.get_app(app_id, account)
        self.update(app, **kwargs)
        return app

    def copy_app(self, app_id: UUID, account: Account) -> App:
        """Copy an existing Agent and its configuration to create a new Agent."""
        # 1. Get app and its draft config, and validate permissions
        app = self.get_app(app_id, account)
        draft_app_config = app.draft_app_config

        # 2. Convert to dict and remove unused fields
        app_dict = app.__dict__.copy()
        draft_app_config_dict = draft_app_config.__dict__.copy()

        # 3. Remove unused fields
        app_remove_fields = [
            "id", "app_config_id", "draft_app_config_id", "debug_conversation_id",
            "status", "updated_at", "created_at", "_sa_instance_state",
        ]
        draft_app_config_remove_fields = [
            "id", "app_id", "version", "updated_at", "created_at", "_sa_instance_state",
        ]
        remove_fields(app_dict, app_remove_fields)
        remove_fields(draft_app_config_dict, draft_app_config_remove_fields)

        # 4. Start DB auto-commit context
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

            # 7. Update new app's draft config ID
            new_app.draft_app_config_id = new_draft_app_config.id

        # 8. Return the newly created app
        return new_app

    def get_apps_with_page(self, req: GetAppsWithPageReq, account: Account) -> tuple[list[App], Paginator]:
        """Get paginated list of applications under the current account."""
        # 1. Build paginator
        paginator = Paginator(db=self.db, req=req)

        # 2. Build filters
        filters = [App.account_id == account.id]
        if req.search_word.data:
            filters.append(App.name.ilike(f"%{req.search_word.data}%"))

        # 3. Execute pagination
        apps = paginator.paginate(
            self.db.session.query(App).filter(*filters).order_by(desc("created_at"))
        )

        return apps, paginator

    def get_draft_app_config(self, app_id: UUID, account: Account) -> dict[str, Any]:
        """Get the draft configuration of the specified app."""
        app = self.get_app(app_id, account)
        return self.app_config_service.get_draft_app_config(app)

    def update_draft_app_config(
            self,
            app_id: UUID,
            draft_app_config: dict[str, Any],
            account: Account,
    ) -> AppConfigVersion:
        """Update the latest draft configuration of the specified app."""
        # 1. Get app info and validate
        app = self.get_app(app_id, account)

        # 2. Validate the incoming draft configuration
        draft_app_config = self._validate_draft_app_config(draft_app_config, account)

        # 3. Get current draft record for this app
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            # TODO: Temporary patch since server_onupdate is used; updated_at must be passed manually for now
            updated_at=datetime.now(),
            **draft_app_config,
        )

        return draft_app_config_record

    def publish_draft_app_config(self, app_id: UUID, account: Account) -> App:
        """Publish or update an app's draft configuration as its runtime configuration."""
        # 1. Get app and its draft config
        app = self.get_app(app_id, account)
        draft_app_config = self.get_draft_app_config(app_id, account)

        # 2. Create runtime configuration (do not delete historical runtime configs for now)
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
            # TODO: When workflow module is complete, this may change
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

        # 3. Update app's runtime config ID and status
        self.update(app, app_config_id=app_config.id, status=AppStatus.PUBLISHED)

        # 4. First delete existing dataset associations
        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id,
            ).delete()

        # 5. Add new dataset associations
        for dataset in draft_app_config["datasets"]:
            self.create(AppDatasetJoin, app_id=app_id, dataset_id=dataset["id"])

        # 6. Copy draft config and remove id, version, config_type, timestamps, etc.
        draft_app_config_copy = app.draft_app_config.__dict__.copy()
        remove_fields(
            draft_app_config_copy,
            ["id", "version", "config_type", "updated_at", "created_at", "_sa_instance_state"],
        )

        # 7. Get current max published version
        max_version = self.db.session.query(func.coalesce(func.max(AppConfigVersion.version), 0)).filter(
            AppConfigVersion.app_id == app_id,
            AppConfigVersion.config_type == AppConfigType.PUBLISHED,
        ).scalar()

        # 8. Add a published history record
        self.create(
            AppConfigVersion,
            version=max_version + 1,
            config_type=AppConfigType.PUBLISHED,
            **draft_app_config_copy,
        )

        return app

    def cancel_publish_app_config(self, app_id: UUID, account: Account) -> App:
        """Cancel publication of the specified app configuration."""
        # 1. Get app info and validate permissions
        app = self.get_app(app_id, account)

        # 2. Check whether the app is currently published
        if app.status != AppStatus.PUBLISHED:
            raise FailException("The application has not been published; cannot cancel publication.")

        # 3. Set status to DRAFT and clear runtime config ID
        self.update(app, status=AppStatus.DRAFT, app_config_id=None)

        # 4. Delete dataset associations
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
        """Get paginated list of published configuration histories for a given app."""
        # 1. Validate app permissions
        self.get_app(app_id, account)

        # 2. Build paginator
        paginator = Paginator(db=self.db, req=req)

        # 3. Paginate and fetch data
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
        """Fallback a specific published configuration version to the current draft."""
        # 1. Validate app permissions and get app
        app = self.get_app(app_id, account)

        # 2. Query the specified historical config version
        app_config_version = self.get(AppConfigVersion, app_config_version_id)
        if not app_config_version:
            raise NotFoundException("The specified historical configuration version does not exist.")

        # 3. Convert to dict and remove fields (filter out deleted tools, datasets, workflows)
        draft_app_config_dict = app_config_version.__dict__.copy()
        remove_fields(
            draft_app_config_dict,
            ["id", "app_id", "version", "config_type", "updated_at", "created_at", "_sa_instance_state"],
        )

        # 4. Validate the historical configuration
        draft_app_config_dict = self._validate_draft_app_config(draft_app_config_dict, account)

        # 5. Update the app's draft config
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            # TODO: patch for updating timestamp
            updated_at=datetime.now(),
            **draft_app_config_dict,
        )

        return draft_app_config_record

    def get_debug_conversation_summary(self, app_id: UUID, account: Account) -> str:
        """Get the long-term memory (summary) of the debug conversation for the given app."""
        # 1. Validate app permissions
        app = self.get_app(app_id, account)

        # 2. Get draft config and check whether long-term memory is enabled
        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("Long-term memory is not enabled for this application.")

        return app.debug_conversation.summary

    def update_debug_conversation_summary(self, app_id: UUID, summary: str, account: Account) -> Conversation:
        """Update the debug conversation long-term memory for the given app."""
        # 1. Validate app permissions
        app = self.get_app(app_id, account)

        # 2. Get draft config and verify long-term memory is enabled
        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("Long-term memory is not enabled for this application.")

        # 3. Update long-term memory summary
        debug_conversation = app.debug_conversation
        self.update(debug_conversation, summary=summary)

        return debug_conversation

    def delete_debug_conversation(self, app_id: UUID, account: Account) -> App:
        """Delete the debug conversation of the specified app."""
        # 1. Validate app permissions
        app = self.get_app(app_id, account)

        # 2. If debug_conversation_id is not set, there is nothing to delete
        if not app.debug_conversation_id:
            return app

        # 3. Reset debug_conversation_id to None
        self.update(app, debug_conversation_id=None)

        return app

    def debug_chat(self, app_id: UUID, query: str, account: Account) -> Generator:
        """Start a debug chat with a given app using the provided query."""
        # 1. Validate app permissions
        app = self.get_app(app_id, account)

        # 2. Get the latest draft config for this app
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

        # 5. Load LLM from language model service based on draft model config
        llm = self.language_model_service.load_language_model(draft_app_config.get("model_config", {}))

        # 6. Instantiate TokenBufferMemory to extract short-term memory
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=debug_conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=draft_app_config["dialog_round"],
        )

        # 7. Convert tools from draft config into LangChain tools
        tools = self.app_config_service.get_langchain_tools_by_tools_config(draft_app_config["tools"])

        # 8. Check whether a dataset (knowledge base) is configured
        if draft_app_config["datasets"]:
            # 9. Build a LangChain retrieval tool
            dataset_retrieval = self.retrieval_service.create_langchain_tool_from_search(
                flask_app=current_app._get_current_object(),
                dataset_ids=[dataset["id"] for dataset in draft_app_config["datasets"]],
                account_id=account.id,
                retrival_source=RetrievalSource.APP,
                **draft_app_config["retrieval_config"],
            )
            tools.append(dataset_retrieval)

        # 10. Decide which Agent implementation to use based on tool_call support
        agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL in llm.features else ReACTAgent
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

        agent_thoughts = {}
        for agent_thought in agent.stream({
            "messages": [HumanMessage(query)],
            "history": history,
            "long_term_memory": debug_conversation.summary,
        }):
            # 11. Extract thought and answer
            event_id = str(agent_thought.id)

            # 12. Store agent_thought for persistence
            if agent_thought.event != QueueEvent.PING:
                # 13. Only AGENT_MESSAGE events are accumulated; others overwrite
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    if event_id not in agent_thoughts:
                        # 14. Initialize agent message event
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 15. Accumulate agent message
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

        # 22. Save message and reasoning process to DB
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
        """Stop a debug session for the given app and task ID, interrupting streaming events."""
        # 1. Validate app permissions
        self.get_app(app_id, account)

        # 2. Use AgentQueueManager to stop the specific task
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.DEBUGGER, account.id)

    def get_debug_conversation_messages_with_page(
            self,
            app_id: UUID,
            req: GetDebugConversationMessagesWithPageReq,
            account: Account
    ) -> tuple[list[Message], Paginator]:
        """Get paginated list of debug conversation messages for the given app."""
        # 1. Validate app permissions
        app = self.get_app(app_id, account)

        # 2. Get debug conversation
        debug_conversation = app.debug_conversation

        # 3. Build paginator and filter by cursor conditions
        paginator = Paginator(db=self.db, req=req)
        filters = []
        if req.created_at.data:
            # 4. Convert timestamp to datetime
            created_at_datetime = datetime.fromtimestamp(req.created_at.data)
            filters.append(Message.created_at <= created_at_datetime)

        # 5. Execute pagination and query messages
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
        """Validate incoming draft configuration and return sanitized data."""
        # 1. Validate that at least one acceptable field is present
        acceptable_fields = [
            "model_config", "dialog_round", "preset_prompt",
            "tools", "workflows", "datasets", "retrieval_config",
            "long_term_memory", "opening_statement", "opening_questions",
            "speech_to_text", "text_to_speech", "suggested_after_answer", "review_config",
        ]

        # 2. Validate that draft_app_config is a dict and only contains acceptable fields
        if (
                not draft_app_config
                or not isinstance(draft_app_config, dict)
                or set(draft_app_config.keys()) - set(acceptable_fields)
        ):
            raise ValidateErrorException("Draft configuration fields are invalid. Please check and try again.")

        # 3. Validate model_config: provider/model are strictly validated, parameters are lenient with defaults
        if "model_config" in draft_app_config:
            # 3.1 Get model_config and check type
            model_config = draft_app_config["model_config"]
            if not isinstance(model_config, dict):
                raise ValidateErrorException("Model configuration format is incorrect, please verify and try again.")

            # 3.2 Validate model_config keys
            if set(model_config.keys()) != {"provider", "model", "parameters"}:
                raise ValidateErrorException("Model configuration keys are incorrect, please verify and try again.")

            # 3.3 Validate provider field
            if not model_config["provider"] or not isinstance(model_config["provider"], str):
                raise ValidateErrorException("Model provider type must be a string.")
            provider = self.language_model_manager.get_provider(model_config["provider"])
            if not provider:
                raise ValidateErrorException("The model provider does not exist, please verify and try again.")

            # 3.4 Validate model field
            if not model_config["model"] or not isinstance(model_config["model"], str):
                raise ValidateErrorException("Model name must be a string.")
            model_entity = provider.get_model_entity(model_config["model"])
            if not model_entity:
                raise ValidateErrorException("The specified model does not exist for this provider, please verify.")

            # 3.5 Validate parameters: if invalid, use defaults; also drop extra fields and fill missing ones
            parameters = {}
            for parameter in model_entity.parameters:
                # 3.6 Get parameter value or default
                parameter_value = model_config["parameters"].get(parameter.name, parameter.default)

                # 3.7 If parameter is required
                if parameter.required:
                    # 3.8 Required parameters cannot be None; if None, set to default
                    if parameter_value is None:
                        parameter_value = parameter.default
                    else:
                        # 3.9 If not None, validate type; if mismatched, use default
                        if get_value_type(parameter_value) != parameter.type.value:
                            parameter_value = parameter.default
                else:
                    # 3.10 For optional parameters, validate type only when not None
                    if parameter_value is not None:
                        if get_value_type(parameter_value) != parameter.type.value:
                            parameter_value = parameter.default

                # 3.11 If options are provided, value must be one of them
                if parameter.options and parameter_value not in parameter.options:
                    parameter_value = parameter.default

                # 3.12 For INT/FLOAT, validate min/max if present
                if parameter.type in [ModelParameterType.INT, ModelParameterType.FLOAT] and parameter_value is not None:
                    # 3.13 Validate min/max
                    if (
                            (parameter.min is not None and parameter_value < parameter.min)
                            or (parameter.max is not None and parameter_value > parameter.max)
                    ):
                        parameter_value = parameter.default

                parameters[parameter.name] = parameter_value

            # 3.13 Overwrite model_config.parameters with sanitized parameters
            model_config["parameters"] = parameters
            draft_app_config["model_config"] = model_config

        # 4. Validate dialog_round range and type
        if "dialog_round" in draft_app_config:
            dialog_round = draft_app_config["dialog_round"]
            if not isinstance(dialog_round, int) or not (0 <= dialog_round <= 100):
                raise ValidateErrorException("Dialog round count must be an integer in the range 0–100.")

        # 5. Validate preset_prompt
        if "preset_prompt" in draft_app_config:
            preset_prompt = draft_app_config["preset_prompt"]
            if not isinstance(preset_prompt, str) or len(preset_prompt) > 2000:
                raise ValidateErrorException(
                    "Preset prompt must be a string with length between 0 and 2000 characters.")

        # 6. Validate tools
        if "tools" in draft_app_config:
            tools = draft_app_config["tools"]
            validate_tools = []

            # 6.1 tools must be a list; empty list means no tools bound
            if not isinstance(tools, list):
                raise ValidateErrorException("Tools must be provided as a list.")
            # 6.2 At most 5 tools can be bound
            if len(tools) > 5:
                raise ValidateErrorException("An Agent cannot bind more than 5 tools.")
            # 6.3 Validate each tool
            for tool in tools:
                # 6.4 Tool must be non-empty and a dict
                if not tool or not isinstance(tool, dict):
                    raise ValidateErrorException("Tool binding parameters are invalid.")
                # 6.5 Keys must be {type, provider_id, tool_id, params}
                if set(tool.keys()) != {"type", "provider_id", "tool_id", "params"}:
                    raise ValidateErrorException("Tool binding parameters are invalid.")
                # 6.6 type must be builtin_tool or api_tool
                if tool["type"] not in ["builtin_tool", "api_tool"]:
                    raise ValidateErrorException("Tool binding parameters are invalid.")
                # 6.7 Validate provider_id and tool_id
                if (
                        not tool["provider_id"]
                        or not tool["tool_id"]
                        or not isinstance(tool["provider_id"], str)
                        or not isinstance(tool["tool_id"], str)
                ):
                    raise ValidateErrorException("Tool provider or tool identifier parameters are invalid.")
                # 6.8 params must be a dict
                if not isinstance(tool["params"], dict):
                    raise ValidateErrorException("Tool custom parameters must be a dictionary.")
                # 6.9 Validate tool existence (builtin vs API tool)
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

            # 6.10 Validate no duplicate bindings
            check_tools = [f"{tool['provider_id']}_{tool['tool_id']}" for tool in validate_tools]
            if len(set(check_tools)) != len(validate_tools):
                raise ValidateErrorException("Duplicate tool bindings detected.")

            # 6.11 Overwrite tools with validated list
            draft_app_config["tools"] = validate_tools

        # TODO: 7. Validate workflows once workflow module is complete
        if "workflows" in draft_app_config:
            draft_app_config["workflows"] = []

        # 8. Validate datasets (knowledge base list)
        if "datasets" in draft_app_config:
            datasets = draft_app_config["datasets"]

            # 8.1 datasets must be a list
            if not isinstance(datasets, list):
                raise ValidateErrorException("Dataset binding list format is invalid.")
            # 8.2 At most 5 datasets can be bound
            if len(datasets) > 5:
                raise ValidateErrorException("An Agent cannot bind more than 5 datasets.")
            # 8.3 Validate each dataset ID
            for dataset_id in datasets:
                try:
                    UUID(dataset_id)
                except Exception:
                    raise ValidateErrorException("Each dataset ID must be a valid UUID string.")
            # 8.4 Check for duplicates
            if len(set(datasets)) != len(datasets):
                raise ValidateErrorException("Duplicate dataset bindings detected.")
            # 8.5 Filter datasets by ownership (only keep datasets belonging to this account)
            dataset_records = self.db.session.query(Dataset).filter(
                Dataset.id.in_(datasets),
                Dataset.account_id == account.id,
            ).all()
            dataset_sets = set([str(dataset_record.id) for dataset_record in dataset_records])
            draft_app_config["datasets"] = [dataset_id for dataset_id in datasets if dataset_id in dataset_sets]

        # 9. Validate retrieval_config
        if "retrieval_config" in draft_app_config:
            retrieval_config = draft_app_config["retrieval_config"]

            # 9.1 Non-empty dict
            if not retrieval_config or not isinstance(retrieval_config, dict):
                raise ValidateErrorException("Retrieval configuration format is invalid.")
            # 9.2 Must contain correct keys
            if set(retrieval_config.keys()) != {"retrieval_strategy", "k", "score"}:
                raise ValidateErrorException("Retrieval configuration format is invalid.")
            # 9.3 Validate retrieval strategy
            if retrieval_config["retrieval_strategy"] not in ["semantic", "full_text", "hybrid"]:
                raise ValidateErrorException("Retrieval strategy is invalid.")
            # 9.4 Validate k (max recall)
            if not isinstance(retrieval_config["k"], int) or not (0 <= retrieval_config["k"] <= 10):
                raise ValidateErrorException("Max recall (k) must be an integer between 0 and 10.")
            # 9.5 Validate score (min similarity)
            if not isinstance(retrieval_config["score"], float) or not (0 <= retrieval_config["score"] <= 1):
                raise ValidateErrorException("Minimum similarity score must be between 0 and 1.")

        # 10. Validate long_term_memory config
        if "long_term_memory" in draft_app_config:
            long_term_memory = draft_app_config["long_term_memory"]

            # 10.1 Must be a non-empty dict
            if not long_term_memory or not isinstance(long_term_memory, dict):
                raise ValidateErrorException("Long-term memory configuration format is invalid.")
            # 10.2 Must have correct keys and types
            if (
                    set(long_term_memory.keys()) != {"enable"}
                    or not isinstance(long_term_memory["enable"], bool)
            ):
                raise ValidateErrorException("Long-term memory configuration format is invalid.")

        # 11. Validate opening_statement
        if "opening_statement" in draft_app_config:
            opening_statement = draft_app_config["opening_statement"]

            # 11.1 Must be string up to 2000 characters
            if not isinstance(opening_statement, str) or len(opening_statement) > 2000:
                raise ValidateErrorException("Opening statement length must be between 0 and 2000 characters.")

        # 12. Validate opening_questions
        if "opening_questions" in draft_app_config:
            opening_questions = draft_app_config["opening_questions"]

            # 12.1 Must be a list with at most 3 items
            if not isinstance(opening_questions, list) or len(opening_questions) > 3:
                raise ValidateErrorException("Opening questions must be a list with at most 3 items.")
            # 12.2 Each item must be a string
            for opening_question in opening_questions:
                if not isinstance(opening_question, str):
                    raise ValidateErrorException("Each opening question must be a string.")

        # 13. Validate speech_to_text
        if "speech_to_text" in draft_app_config:
            speech_to_text = draft_app_config["speech_to_text"]

            # 13.1 Must be a non-empty dict
            if not speech_to_text or not isinstance(speech_to_text, dict):
                raise ValidateErrorException("Speech-to-text configuration format is invalid.")
            # 13.2 Must have correct keys and types
            if (
                    set(speech_to_text.keys()) != {"enable"}
                    or not isinstance(speech_to_text["enable"], bool)
            ):
                raise ValidateErrorException("Speech-to-text configuration format is invalid.")

        # 14. Validate text_to_speech
        if "text_to_speech" in draft_app_config:
            text_to_speech = draft_app_config["text_to_speech"]

            # 14.1 Must be a dict
            if not isinstance(text_to_speech, dict):
                raise ValidateErrorException("Text-to-speech configuration format is invalid.")
            # 14.2 Validate keys and types
            if (
                    set(text_to_speech.keys()) != {"enable", "voice", "auto_play"}
                    or not isinstance(text_to_speech["enable"], bool)
                    # TODO: Add more voices when multimodal Agent is implemented
                    or text_to_speech["voice"] not in ["echo"]
                    or not isinstance(text_to_speech["auto_play"], bool)
            ):
                raise ValidateErrorException("Text-to-speech configuration format is invalid.")

        # 15. Validate suggested_after_answer
        if "suggested_after_answer" in draft_app_config:
            suggested_after_answer = draft_app_config["suggested_after_answer"]

            # 15.1 Must be a non-empty dict
            if not suggested_after_answer or not isinstance(suggested_after_answer, dict):
                raise ValidateErrorException("Suggested-after-answer configuration format is invalid.")
            # 15.2 Must contain correct keys and types
            if (
                    set(suggested_after_answer.keys()) != {"enable"}
                    or not isinstance(suggested_after_answer["enable"], bool)
            ):
                raise ValidateErrorException("Suggested-after-answer configuration format is invalid.")

        # 16. Validate review_config
        if "review_config" in draft_app_config:
            review_config = draft_app_config["review_config"]

            # 16.1 Must be a non-empty dict
            if not review_config or not isinstance(review_config, dict):
                raise ValidateErrorException("Review configuration format is invalid.")
            # 16.2 Validate keys
            if set(review_config.keys()) != {"enable", "keywords", "inputs_config", "outputs_config"}:
                raise ValidateErrorException("Review configuration format is invalid.")
            # 16.3 Validate enable
            if not isinstance(review_config["enable"], bool):
                raise ValidateErrorException("review.enable must be a boolean.")
            # 16.4 Validate keywords
            if (
                    not isinstance(review_config["keywords"], list)
                    or (review_config["enable"] and len(review_config["keywords"]) == 0)
                    or len(review_config["keywords"]) > 100
            ):
                raise ValidateErrorException("review.keywords must be a non-empty list with at most 100 items.")
            for keyword in review_config["keywords"]:
                if not isinstance(keyword, str):
                    raise ValidateErrorException("Each review keyword must be a string.")
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
                raise ValidateErrorException("review.outputs_config must be a dict with valid fields.")
            # 16.7 If review is enabled, at least one of inputs/outputs must be enabled
            if review_config["enable"]:
                if (
                        review_config["inputs_config"]["enable"] is False
                        and review_config["outputs_config"]["enable"] is False
                ):
                    raise ValidateErrorException("At least one of input review or output review must be enabled.")

                if (
                        review_config["inputs_config"]["enable"]
                        and review_config["inputs_config"]["preset_response"].strip() == ""
                ):
                    raise ValidateErrorException("Preset response for input review must not be empty.")

        return draft_app_config
