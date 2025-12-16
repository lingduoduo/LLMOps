#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : app_service.py
"""
import json
import os
from dataclasses import dataclass
from datetime import datetime
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
from sqlalchemy.orm import joinedload

from internal.core.agent.agents import FunctionCallAgent, AgentQueueManager, ReACTAgent
from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.language_model import LanguageModelManager
from internal.core.language_model.entities.model_entity import ModelParameterType, ModelFeature
from internal.core.memory import TokenBufferMemory
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.entity.ai_entity import OPTIMIZE_PROMPT_TEMPLATE
from internal.entity.app_entity import AppStatus, AppConfigType, DEFAULT_APP_CONFIG
from internal.entity.app_entity import GENERATE_ICON_PROMPT_TEMPLATE
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.entity.dataset_entity import RetrievalSource
from internal.entity.workflow_entity import WorkflowStatus
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


@inject
@dataclass
class AppService(BaseService):
    """Application service logic"""
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
        """Create an Agent app using AI based on the given name/description/account_id"""
        # 1. Create an LLM used to generate the icon prompt and the preset prompt
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.8)

        # 2. Create the DallE API wrapper
        dalle_api_wrapper = DallEAPIWrapper(model="dall-e-3", size="1024x1024")

        # 3. Build the icon generation chain
        generate_icon_chain = (
                ChatPromptTemplate.from_template(GENERATE_ICON_PROMPT_TEMPLATE)
                | llm
                | StrOutputParser()
                | dalle_api_wrapper.run
        )

        # 4. Build the preset prompt generation chain
        generate_preset_prompt_chain = (
                ChatPromptTemplate.from_messages([
                    ("system", OPTIMIZE_PROMPT_TEMPLATE),
                    ("human", "App name: {name}\n\nApp description: {description}")
                ])
                | llm
                | StrOutputParser()
        )

        # 5. Create a parallel chain to run both chains at the same time
        generate_app_config_chain = RunnableParallel({
            "icon": generate_icon_chain,
            "preset_prompt": generate_preset_prompt_chain,
        })
        app_config = generate_app_config_chain.invoke({"name": name, "description": description})

        # 6. Download the image and upload it to Tencent COS
        icon_response = requests.get(app_config.get("icon"))
        if icon_response.status_code == 200:
            icon_content = icon_response.content
        else:
            raise FailException("Failed to generate the app icon")

        account = self.db.session.query(Account).get(account_id)

        internal_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_dir = os.path.join(internal_path, "storage", "icons")
        os.makedirs(icon_dir, exist_ok=True)
        icon_filename = f"{account_id}_icon.png"
        icon_path = os.path.join(icon_dir, icon_filename)
        with open(icon_path, "wb") as f:
            f.write(icon_content)
        icon = icon_path

        # 7. Enter the DB auto-commit context
        with self.db.auto_commit():
            # 8. Create the app record and flush so we can get app.id
            app = App(
                account_id=account.id,
                name=name,
                icon=icon,
                description=description,
            )
            self.db.session.add(app)
            self.db.session.flush()

            # 9. Create the draft config record
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

            # 10. Update the app's draft config ID
            app.draft_app_config_id = app_config_version.id

    def create_app(self, req: CreateAppReq, account: Account) -> App:
        """Create an Agent app"""
        # 1. Enter the DB auto-commit context
        with self.db.auto_commit():
            # 2. Create the app record and flush so we can get app.id
            app = App(
                account_id=account.id,
                name=req.name.data,
                icon=req.icon.data,
                description=req.description.data,
                status=AppStatus.DRAFT,
            )
            self.db.session.add(app)
            self.db.session.flush()

            # 3. Create the draft config record
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

        # 5. Return the created app record
        return app

    def get_app(self, app_id: UUID, account: Account) -> App:
        """Get the basic app info by app_id"""
        # 1. Query the DB for the app
        app = self.get(App, app_id)

        # 2. Check whether the app exists
        if not app:
            raise NotFoundException("The app does not exist. Please verify and try again.")

        # 3. Check whether the current account has permission to access the app
        if app.account_id != account.id:
            raise ForbiddenException("The current account does not have permission to access this app.")

        return app

    def delete_app(self, app_id: UUID, account: Account) -> App:
        """Delete the specified app (currently only deletes the app base record)"""
        app = self.get_app(app_id, account)
        self.delete(app)
        return app

    def update_app(self, app_id: UUID, account: Account, **kwargs) -> App:
        """Update the specified app by app_id"""
        app = self.get_app(app_id, account)
        self.update(app, **kwargs)
        return app

    def copy_app(self, app_id: UUID, account: Account) -> App:
        """Copy the Agent/app info and create a new Agent"""
        # 1. Get App + draft config and verify permission
        app = self.get_app(app_id, account)
        draft_app_config = app.draft_app_config

        # 2. Convert records to dicts and remove unnecessary fields
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

        # 4. Enter the DB auto-commit context
        with self.db.auto_commit():
            # 5. Create a new app record
            new_app = App(**app_dict, status=AppStatus.DRAFT)
            self.db.session.add(new_app)
            self.db.session.flush()

            # 6. Create the draft config
            new_draft_app_config = AppConfigVersion(
                **draft_app_config_dict,
                app_id=new_app.id,
                version=0,
            )
            self.db.session.add(new_draft_app_config)
            self.db.session.flush()

            # 7. Update the app's draft config ID
            new_app.draft_app_config_id = new_draft_app_config.id

        # 8. Return the newly created app
        return new_app

    def get_apps_with_page(self, req: GetAppsWithPageReq, account: Account) -> tuple[list[App], Paginator]:
        """Get a paginated list of apps under the current logged-in account"""
        # 1. Build the paginator
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
        """Get the draft config for the specified app"""
        app = self.get_app(app_id, account)
        return self.app_config_service.get_draft_app_config(app)

    def update_draft_app_config(
            self,
            app_id: UUID,
            draft_app_config: dict[str, Any],
            account: Account,
    ) -> AppConfigVersion:
        """Update the latest draft config for the specified app"""
        # 1. Get app info and validate
        app = self.get_app(app_id, account)

        # 2. Validate the provided draft config
        draft_app_config = self._validate_draft_app_config(draft_app_config, account)

        # 3. Get the latest draft config record for the app
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            **draft_app_config,
        )

        return draft_app_config_record

    def publish_draft_app_config(self, app_id: UUID, account: Account) -> App:
        """Publish/update the app draft config as the runtime config"""
        # 1. Get the app info and the draft config
        app = self.get_app(app_id, account)
        draft_app_config = self.get_draft_app_config(app_id, account)

        # 2. Create the runtime config (for now, we do not delete historical runtime configs)
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

        # 3. Update the app's runtime config association and status
        self.update(app, app_config_id=app_config.id, status=AppStatus.PUBLISHED)

        # 4. Delete existing dataset join records
        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id,
            ).delete()

        # 5. Create new dataset join records
        for dataset in draft_app_config["datasets"]:
            self.create(AppDatasetJoin, app_id=app_id, dataset_id=dataset["id"])

        # 6. Copy the draft config record and remove id/version/type/timestamps fields
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

        # 8. Insert a publish-history config record
        self.create(
            AppConfigVersion,
            version=max_version + 1,
            config_type=AppConfigType.PUBLISHED,
            **draft_app_config_copy,
        )

        return app

    def cancel_publish_app_config(self, app_id: UUID, account: Account) -> App:
        """Cancel publishing for the specified app config"""
        # 1. Get app info and validate permission
        app = self.get_app(app_id, account)

        # 2. Check whether the app is currently published
        if app.status != AppStatus.PUBLISHED:
            raise FailException("The app is not published. Please verify and try again.")

        # 3. Set the app status back to draft and clear the runtime config association
        self.update(app, status=AppStatus.DRAFT, app_config_id=None)

        # 4. Delete dataset join records for the app
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
        """Get the paginated list of publish-history config versions for the specified app"""
        # 1. Get app info and validate permission
        self.get_app(app_id, account)

        # 2. Build the paginator
        paginator = Paginator(db=self.db, req=req)

        # 3. Execute pagination and fetch data
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
        """Rollback a specific historical config version to the draft"""
        # 1. Validate permission and fetch app info
        app = self.get_app(app_id, account)

        # 2. Query the specified historical config version by id
        app_config_version = self.get(AppConfigVersion, app_config_version_id)
        if not app_config_version:
            raise NotFoundException("The specified historical config version does not exist.")

        # 3. Prepare the historical config dict (remove deleted tools/datasets/workflows)
        draft_app_config_dict = app_config_version.__dict__.copy()
        remove_fields(
            draft_app_config_dict,
            ["id", "app_id", "version", "config_type", "updated_at", "created_at", "_sa_instance_state"],
        )

        # 4. Validate the historical config
        draft_app_config_dict = self._validate_draft_app_config(draft_app_config_dict, account)

        # 5. Update the draft config
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            **draft_app_config_dict,
        )

        return draft_app_config_record

    def get_debug_conversation_summary(self, app_id: UUID, account: Account) -> str:
        """Get the long-term memory (summary) of the app's debug conversation"""
        # 1. Get app info and validate permission
        app = self.get_app(app_id, account)

        # 2. Get the draft config and verify that long-term memory is enabled
        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("Long-term memory is not enabled for this app, so it cannot be retrieved.")

        return app.debug_conversation.summary

    def update_debug_conversation_summary(self, app_id: UUID, summary: str, account: Account) -> Conversation:
        """Update the long-term memory (summary) of the app's debug conversation"""
        # 1. Get app info and validate permission
        app = self.get_app(app_id, account)

        # 2. Get the draft config and verify that long-term memory is enabled
        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("Long-term memory is not enabled for this app, so it cannot be updated.")

        # 3. Update the debug conversation long-term memory
        debug_conversation = app.debug_conversation
        self.update(debug_conversation, summary=summary)

        return debug_conversation

    def delete_debug_conversation(self, app_id: UUID, account: Account) -> App:
        """Delete (reset) the debug conversation for the specified app"""
        # 1. Get app info and validate permission
        app = self.get_app(app_id, account)

        # 2. If debug_conversation_id is missing, there is no conversation; no action needed
        if not app.debug_conversation_id:
            return app

        # 3. Otherwise reset debug_conversation_id to None
        self.update(app, debug_conversation_id=None)

        return app

    def debug_chat(self, app_id: UUID, query: str, account: Account) -> Generator:
        """Start a debug chat session for the specified app using the given query"""
        # 1. Get app info and validate permission
        app = self.get_app(app_id, account)

        # 2. Get the latest draft config
        draft_app_config = self.get_draft_app_config(app_id, account)

        # 3. Get the app's debug conversation
        debug_conversation = app.debug_conversation

        # 4. Create a message record
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
        llm = self.language_model_service.load_language_model(draft_app_config.get("model_config", {}))

        # 6. Instantiate TokenBufferMemory to retrieve short-term memory
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=debug_conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=draft_app_config["dialog_round"],
        )

        # 7. Convert the draft config tools into LangChain tools
        tools = self.app_config_service.get_langchain_tools_by_tools_config(draft_app_config["tools"])

        # 8. Check whether any datasets are linked
        if draft_app_config["datasets"]:
            # 9. Build the LangChain dataset retrieval tool
            dataset_retrieval = self.retrieval_service.create_langchain_tool_from_search(
                flask_app=current_app._get_current_object(),
                dataset_ids=[dataset["id"] for dataset in draft_app_config["datasets"]],
                account_id=account.id,
                retrival_source=RetrievalSource.APP,
                **draft_app_config["retrieval_config"],
            )
            tools.append(dataset_retrieval)

        # 10. If workflows are linked, convert them into tools and add to tools
        if draft_app_config["workflows"]:
            workflow_tools = self.app_config_service.get_langchain_tools_by_workflow_ids(
                [workflow["id"] for workflow in draft_app_config["workflows"]]
            )
            tools.extend(workflow_tools)

        # 10. Choose the agent implementation depending on whether the LLM supports tool calling
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

            # 12. Fill agent_thought data so it can be persisted by the conversation service
            if agent_thought.event != QueueEvent.PING:
                # 13. For AGENT_MESSAGE events we append; for other events we overwrite
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    if event_id not in agent_thoughts:
                        # 14. Initialize the agent message event
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 15. Append the agent message content
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
                            # Agent step stats
                            "total_token_count": agent_thought.total_token_count,
                            "total_price": agent_thought.total_price,
                            "latency": agent_thought.latency,
                        })
                else:
                    # 16. Handle other event types
                    agent_thoughts[event_id] = agent_thought

            data = {
                **agent_thought.model_dump(include={
                    "event", "thought", "observation", "tool", "tool_input", "answer",
                    "total_token_count", "total_price", "latency",
                }),
                "id": event_id,
                "conversation_id": str(debug_conversation.id),
                "message_id": str(message.id),
                "task_id": str(agent_thought.task_id),
            }
            yield f"event: {agent_thought.event}\ndata:{json.dumps(data)}\n\n"

        # 22. Persist the message and the agent reasoning steps to the DB
        self.conversation_service.save_agent_thoughts(
            account_id=account.id,
            app_id=app.id,
            app_config=draft_app_config,
            conversation_id=debug_conversation.id,
            message_id=message.id,
            agent_thoughts=[agent_thought for agent_thought in agent_thoughts.values()],
        )

    def stop_debug_chat(self, app_id: UUID, task_id: UUID, account: Account) -> None:
        """Stop the debug chat for the specified app/task/account and interrupt the streaming response"""
        # 1. Get app info and validate permission
        self.get_app(app_id, account)

        # 2. Ask the agent queue manager to stop the specific task
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.DEBUGGER, account.id)

    def get_debug_conversation_messages_with_page(
            self,
            app_id: UUID,
            req: GetDebugConversationMessagesWithPageReq,
            account: Account
    ) -> tuple[list[Message], Paginator]:
        """Get a paginated list of debug conversation messages for the specified app"""
        # 1. Get app info and validate permission
        app = self.get_app(app_id, account)

        # 2. Get the app's debug conversation
        debug_conversation = app.debug_conversation

        # 3. Build the paginator and cursor filters
        paginator = Paginator(db=self.db, req=req)
        filters = []
        if req.created_at.data:
            # 4. Convert the timestamp to DateTime
            created_at_datetime = datetime.fromtimestamp(req.created_at.data)
            filters.append(Message.created_at <= created_at_datetime)

        # 5. Execute pagination and query data
        messages = paginator.paginate(
            self.db.session.query(Message).options(joinedload(Message.agent_thoughts)).filter(
                Message.conversation_id == debug_conversation.id,
                Message.status.in_([MessageStatus.STOP, MessageStatus.NORMAL]),
                Message.answer != "",
                *filters,
            ).order_by(desc("created_at"))
        )

        return messages, paginator

    def get_published_config(self, app_id: UUID, account: Account) -> dict[str, Any]:
        """Get the published configuration for the specified app"""
        # 1. Get app info and validate permission
        app = self.get_app(app_id, account)

        # 2. Build and return the published config
        return {
            "web_app": {
                "token": app.token_with_default,
                "status": app.status,
            }
        }

    def regenerate_web_app_token(self, app_id: UUID, account: Account) -> str:
        """Regenerate the WebApp token for the specified app"""
        # 1. Get app info and validate permission
        app = self.get_app(app_id, account)

        # 2. Check whether the app is published
        if app.status != AppStatus.PUBLISHED:
            raise FailException("The app is not published, so a WebApp token cannot be generated.")

        # 3. Regenerate the token and update the record
        token = generate_random_string(16)
        self.update(app, token=token)

        return token

    def _validate_draft_app_config(self, draft_app_config: dict[str, Any], account: Account) -> dict[str, Any]:
        """Validate the app draft config payload and return the validated result"""
        # 1. Validate that the draft payload only contains acceptable fields (must update at least one field)
        acceptable_fields = [
            "model_config", "dialog_round", "preset_prompt",
            "tools", "workflows", "datasets", "retrieval_config",
            "long_term_memory", "opening_statement", "opening_questions",
            "speech_to_text", "text_to_speech", "suggested_after_answer", "review_config",
        ]

        # 2. Ensure the provided keys are within the acceptable field set
        if (
                not draft_app_config
                or not isinstance(draft_app_config, dict)
                or set(draft_app_config.keys()) - set(acceptable_fields)
        ):
            raise ValidateErrorException("Invalid draft config fields. Please verify and try again.")

        # 3. Validate model_config: provider/model are strict (raise on error); parameters are lenient and defaulted
        if "model_config" in draft_app_config:
            # 3.1 Get model config and ensure it is a dict
            model_config = draft_app_config["model_config"]
            if not isinstance(model_config, dict):
                raise ValidateErrorException("Invalid model config format. Please verify and try again.")

            # 3.2 Validate required keys
            if set(model_config.keys()) != {"provider", "model", "parameters"}:
                raise ValidateErrorException("Invalid model config keys. Please verify and try again.")

            # 3.3 Validate provider
            if not model_config["provider"] or not isinstance(model_config["provider"], str):
                raise ValidateErrorException("Model provider must be a string.")
            provider = self.language_model_manager.get_provider(model_config["provider"])
            if not provider:
                raise ValidateErrorException("Model provider does not exist. Please verify and try again.")

            # 3.4 Validate model name
            if not model_config["model"] or not isinstance(model_config["model"], str):
                raise ValidateErrorException("Model name must be a string.")
            model_entity = provider.get_model_entity(model_config["model"])
            if not model_entity:
                raise ValidateErrorException("This model does not exist under the specified provider.")

            # 3.5 Validate parameters: default missing/invalid values; remove extra fields; fill defaults
            parameters = {}
            for parameter in model_entity.parameters:
                # 3.6 Read parameter value; default if missing
                parameter_value = model_config["parameters"].get(parameter.name, parameter.default)

                # 3.7 Check whether this parameter is required
                if parameter.required:
                    # 3.8 Required params cannot be None; if None, fall back to default
                    if parameter_value is None:
                        parameter_value = parameter.default
                    else:
                        # 3.9 If non-null, validate type; if invalid, fall back to default
                        if get_value_type(parameter_value) != parameter.type.value:
                            parameter_value = parameter.default
                else:
                    # 3.10 Optional params: validate type when non-null
                    if parameter_value is not None:
                        if get_value_type(parameter_value) != parameter.type.value:
                            parameter_value = parameter.default

                # 3.11 If options exist, value must be within options
                if parameter.options and parameter_value not in parameter.options:
                    parameter_value = parameter.default

                # 3.12 For int/float params, validate min/max when provided
                if parameter.type in [ModelParameterType.INT, ModelParameterType.FLOAT] and parameter_value is not None:
                    # 3.13 Validate min/max bounds
                    if (
                            (parameter.min and parameter_value < parameter.min)
                            or (parameter.max and parameter_value > parameter.max)
                    ):
                        parameter_value = parameter.default

                parameters[parameter.name] = parameter_value

            # 3.13 Override the parameters in model_config with validated params
            model_config["parameters"] = parameters
            draft_app_config["model_config"] = model_config

        # 4. Validate dialog_round: type + range
        if "dialog_round" in draft_app_config:
            dialog_round = draft_app_config["dialog_round"]
            if not isinstance(dialog_round, int) or not (0 <= dialog_round <= 100):
                raise ValidateErrorException("The dialog round range must be 0-100.")

        # 5. Validate preset_prompt
        if "preset_prompt" in draft_app_config:
            preset_prompt = draft_app_config["preset_prompt"]
            if not isinstance(preset_prompt, str) or len(preset_prompt) > 2000:
                raise ValidateErrorException("Preset prompt must be a string with length 0-2000.")

        # 6. Validate tools
        if "tools" in draft_app_config:
            tools = draft_app_config["tools"]
            validate_tools = []

            # 6.1 tools must be a list; empty list means no tools bound
            if not isinstance(tools, list):
                raise ValidateErrorException("Tools must be a list.")
            # 6.2 tools length cannot exceed 5
            if len(tools) > 5:
                raise ValidateErrorException("An agent cannot bind more than 5 tools.")
            # 6.3 Validate each tool item
            for tool in tools:
                # 6.4 tool must be a non-empty dict
                if not tool or not isinstance(tool, dict):
                    raise ValidateErrorException("Invalid bound tool parameters.")
                # 6.5 Required keys: type, provider_id, tool_id, params
                if set(tool.keys()) != {"type", "provider_id", "tool_id", "params"}:
                    raise ValidateErrorException("Invalid bound tool parameters.")
                # 6.6 type must be builtin_tool or api_tool
                if tool["type"] not in ["builtin_tool", "api_tool"]:
                    raise ValidateErrorException("Invalid bound tool parameters.")
                # 6.7 Validate provider_id/tool_id
                if (
                        not tool["provider_id"]
                        or not tool["tool_id"]
                        or not isinstance(tool["provider_id"], str)
                        or not isinstance(tool["tool_id"], str)
                ):
                    raise ValidateErrorException("Invalid tool provider or tool identifier.")
                # 6.8 params must be a dict
                if not isinstance(tool["params"], dict):
                    raise ValidateErrorException("Tool custom params must be a dict.")
                # 6.9 Validate that the referenced tool exists (builtin_tool vs api_tool)
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

            # 6.10 Validate no duplicate bound tools
            check_tools = [f"{tool['provider_id']}_{tool['tool_id']}" for tool in validate_tools]
            if len(set(check_tools)) != len(validate_tools):
                raise ValidateErrorException("Duplicate bound tools are not allowed.")

            # 6.11 Assign validated tools back
            draft_app_config["tools"] = validate_tools

        # 7. Validate workflows: bind only published workflows with correct permissions
        if "workflows" in draft_app_config:
            workflows = draft_app_config["workflows"]

            # 7.1 workflows must be a list
            if not isinstance(workflows, list):
                raise ValidateErrorException("Invalid workflow list format.")
            # 7.2 workflows length cannot exceed 5
            if len(workflows) > 5:
                raise ValidateErrorException("An agent cannot bind more than 5 workflows.")
            # 7.3 Each workflow id must be a UUID
            for workflow_id in workflows:
                try:
                    UUID(workflow_id)
                except Exception as _:
                    raise ValidateErrorException("Workflow IDs must be UUIDs.")
            # 7.4 No duplicates
            if len(set(workflows)) != len(workflows):
                raise ValidateErrorException("Duplicate workflows are not allowed.")
            # 7.5 Validate permissions and published status; filter out non-owned or unpublished workflows
            workflow_records = self.db.session.query(Workflow).filter(
                Workflow.id.in_(workflows),
                Workflow.account_id == account.id,
                Workflow.status == WorkflowStatus.PUBLISHED,
            ).all()
            workflow_sets = set([str(workflow_record.id) for workflow_record in workflow_records])
            draft_app_config["workflows"] = [workflow_id for workflow_id in workflows if workflow_id in workflow_sets]

        # 8. Validate datasets
        if "datasets" in draft_app_config:
            datasets = draft_app_config["datasets"]

            # 8.1 datasets must be a list
            if not isinstance(datasets, list):
                raise ValidateErrorException("Invalid dataset list format.")
            # 8.2 datasets length cannot exceed 5
            if len(datasets) > 5:
                raise ValidateErrorException("An agent cannot bind more than 5 datasets.")
            # 8.3 Each dataset id must be a UUID
            for dataset_id in datasets:
                try:
                    UUID(dataset_id)
                except Exception as e:
                    raise ValidateErrorException("Dataset IDs must be UUIDs.")
            # 8.4 No duplicates
            if len(set(datasets)) != len(datasets):
                raise ValidateErrorException("Duplicate datasets are not allowed.")
            # 8.5 Validate ownership; filter out datasets not owned by current account
            dataset_records = self.db.session.query(Dataset).filter(
                Dataset.id.in_(datasets),
                Dataset.account_id == account.id,
            ).all()
            dataset_sets = set([str(dataset_record.id) for dataset_record in dataset_records])
            draft_app_config["datasets"] = [dataset_id for dataset_id in datasets if dataset_id in dataset_sets]

        # 9. Validate retrieval_config
        if "retrieval_config" in draft_app_config:
            retrieval_config = draft_app_config["retrieval_config"]

            # 9.1 Must be a non-empty dict
            if not retrieval_config or not isinstance(retrieval_config, dict):
                raise ValidateErrorException("Invalid retrieval config format.")
            # 9.2 Required keys
            if set(retrieval_config.keys()) != {"retrieval_strategy", "k", "score"}:
                raise ValidateErrorException("Invalid retrieval config format.")
            # 9.3 Validate strategy
            if retrieval_config["retrieval_strategy"] not in ["semantic", "full_text", "hybrid"]:
                raise ValidateErrorException("Invalid retrieval strategy.")
            # 9.4 Validate k
            if not isinstance(retrieval_config["k"], int) or not (0 <= retrieval_config["k"] <= 10):
                raise ValidateErrorException("Retrieval 'k' must be in range 0-10.")
            # 9.5 Validate score
            if not isinstance(retrieval_config["score"], float) or not (0 <= retrieval_config["score"] <= 1):
                raise ValidateErrorException("Retrieval 'score' must be in range 0-1.")

        # 10. Validate long_term_memory
        if "long_term_memory" in draft_app_config:
            long_term_memory = draft_app_config["long_term_memory"]

            # 10.1 Validate format
            if not long_term_memory or not isinstance(long_term_memory, dict):
                raise ValidateErrorException("Invalid long-term memory config format.")
            # 10.2 Validate keys and types
            if (
                    set(long_term_memory.keys()) != {"enable"}
                    or not isinstance(long_term_memory["enable"], bool)
            ):
                raise ValidateErrorException("Invalid long-term memory config format.")

        # 11. Validate opening_statement
        if "opening_statement" in draft_app_config:
            opening_statement = draft_app_config["opening_statement"]

            # 11.1 Validate type and length
            if not isinstance(opening_statement, str) or len(opening_statement) > 2000:
                raise ValidateErrorException("Opening statement length must be 0-2000.")

        # 12. Validate opening_questions
        if "opening_questions" in draft_app_config:
            opening_questions = draft_app_config["opening_questions"]

            # 12.1 Must be a list with length <= 3
            if not isinstance(opening_questions, list) or len(opening_questions) > 3:
                raise ValidateErrorException("Opening questions cannot exceed 3 items.")
            # 12.2 Each item must be a string
            for opening_question in opening_questions:
                if not isinstance(opening_question, str):
                    raise ValidateErrorException("Each opening question must be a string.")

        # 13. Validate speech_to_text
        if "speech_to_text" in draft_app_config:
            speech_to_text = draft_app_config["speech_to_text"]

            # 13.1 Validate format
            if not speech_to_text or not isinstance(speech_to_text, dict):
                raise ValidateErrorException("Invalid speech-to-text config format.")
            # 13.2 Validate keys and types
            if (
                    set(speech_to_text.keys()) != {"enable"}
                    or not isinstance(speech_to_text["enable"], bool)
            ):
                raise ValidateErrorException("Invalid speech-to-text config format.")

        # 14. Validate text_to_speech
        if "text_to_speech" in draft_app_config:
            text_to_speech = draft_app_config["text_to_speech"]

            # 14.1 Must be a dict
            if not isinstance(text_to_speech, dict):
                raise ValidateErrorException("Invalid text-to-speech config format.")
            # 14.2 Validate fields and types
            if (
                    set(text_to_speech.keys()) != {"enable", "voice", "auto_play"}
                    or not isinstance(text_to_speech["enable"], bool)
                    # todo: add voice options when multimodal Agent is implemented
                    or text_to_speech["voice"] not in ["echo"]
                    or not isinstance(text_to_speech["auto_play"], bool)
            ):
                raise ValidateErrorException("Invalid text-to-speech config format.")

        # 15. Validate suggested_after_answer
        if "suggested_after_answer" in draft_app_config:
            suggested_after_answer = draft_app_config["suggested_after_answer"]

            # 15.1 Validate format
            if not suggested_after_answer or not isinstance(suggested_after_answer, dict):
                raise ValidateErrorException("Invalid suggested-after-answer config format.")
            # 15.2 Validate keys and types
            if (
                    set(suggested_after_answer.keys()) != {"enable"}
                    or not isinstance(suggested_after_answer["enable"], bool)
            ):
                raise ValidateErrorException("Invalid suggested-after-answer config format.")

        # 16. Validate review_config
        if "review_config" in draft_app_config:
            review_config = draft_app_config["review_config"]

            # 16.1 Must be a non-empty dict
            if not review_config or not isinstance(review_config, dict):
                raise ValidateErrorException("Invalid review config format.")
            # 16.2 Required keys
            if set(review_config.keys()) != {"enable", "keywords", "inputs_config", "outputs_config"}:
                raise ValidateErrorException("Invalid review config format.")
            # 16.3 Validate enable
            if not isinstance(review_config["enable"], bool):
                raise ValidateErrorException("Invalid review.enable format.")
            # 16.4 Validate keywords
            if (
                    not isinstance(review_config["keywords"], list)
                    or (review_config["enable"] and len(review_config["keywords"]) == 0)
                    or len(review_config["keywords"]) > 100
            ):
                raise ValidateErrorException("review.keywords must be non-empty (when enabled) and <= 100 items.")
            for keyword in review_config["keywords"]:
                if not isinstance(keyword, str):
                    raise ValidateErrorException("review.keywords items must be strings.")
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
                raise ValidateErrorException("Invalid review.outputs_config format.")
            # 16.7 When review is enabled, at least one of input/output review must be enabled
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
                    raise ValidateErrorException("Input review preset_response cannot be empty.")

        return draft_app_config
