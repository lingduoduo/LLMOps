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
        # 1. Open DB auto-commit context
        with self.db.auto_commit():
            # 2. Create the app record and flush so we can obtain the app ID
            app = App(
                account_id=account.id,
                name=req.name.data,
                icon=req.icon.data,
                description=req.description.data,
                status=AppStatus.DRAFT,
            )
            self.db.session.add(app)
            self.db.session.flush()

            # 3. Add the draft config record
            app_config_version = AppConfigVersion(
                app_id=app.id,
                version=0,
                config_type=AppConfigType.DRAFT,
                **DEFAULT_APP_CONFIG,
            )
            self.db.session.add(app_config_version)
            self.db.session.flush()

            # 4. Set the draft_app_config_id on the app
            app.draft_app_config_id = app_config_version.id

        # 5. Return the created app record
        return app

    def get_app(self, app_id: UUID, account: Account) -> App:
        """Get the basic application information based on the given app ID"""
        # 1. Query the DB for basic app information
        app = self.get(App, app_id)

        # 2. Check whether the app exists
        if not app:
            raise NotFoundException("The application does not exist, please verify and try again")

        # 3. Check whether the current account has access to this app
        if app.account_id != account.id:
            raise ForbiddenException(
                "The current account is not authorized to access this application, please verify and try again")

        return app

    def get_draft_app_config(self, app_id: UUID, account: Account) -> dict[str, Any]:
        """Get the draft configuration of the specified application"""
        app = self.get_app(app_id, account)
        return self.app_config_service.get_draft_app_config(app)

    def update_draft_app_config(
            self,
            app_id: UUID,
            draft_app_config: dict[str, Any],
            account: Account,
    ) -> AppConfigVersion:
        """Update the latest draft configuration of the specified application using the given draft config"""
        # 1. Get and validate the app
        app = self.get_app(app_id, account)

        # 2. Validate the provided draft configuration
        draft_app_config = self._validate_draft_app_config(draft_app_config, account)

        # 3. Get the latest draft config record for this app
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            # todo: Because we currently use server_onupdate, this field needs to be updated manually for now
            updated_at=datetime.now(),
            **draft_app_config,
        )

        return draft_app_config_record

    def publish_draft_app_config(self, app_id: UUID, account: Account) -> App:
        """Publish/update the draft configuration of the specified application as its runtime configuration"""
        # 1. Get the app and its draft configuration
        app = self.get_app(app_id, account)
        draft_app_config = self.get_draft_app_config(app_id, account)

        # 2. Create the runtime config (for now we do not delete old runtime configs)
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
            # todo: This may change once the workflow module is completed
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

        # 3. Update the app's runtime config and status
        self.update(app, app_config_id=app_config.id, status=AppStatus.PUBLISHED)

        # 4. Delete existing knowledge base association records
        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id,
            ).delete()

        # 5. Add new knowledge base association records
        for dataset in draft_app_config["datasets"]:
            self.create(AppDatasetJoin, app_id=app_id, dataset_id=dataset["id"])

        # 6. Get the app draft record and remove id, version, config_type, updated_at, created_at fields
        draft_app_config_copy = app.draft_app_config.__dict__.copy()
        remove_fields = ["id", "version", "config_type", "updated_at", "created_at", "_sa_instance_state"]
        for field in remove_fields:
            draft_app_config_copy.pop(field)

        # 7. Get the current maximum published version number
        max_version = self.db.session.query(func.coalesce(func.max(AppConfigVersion.version), 0)).filter(
            AppConfigVersion.app_id == app_id,
            AppConfigVersion.config_type == AppConfigType.PUBLISHED,
        ).scalar()

        # 8. Insert a new published version history record
        self.create(
            AppConfigVersion,
            version=max_version + 1,
            config_type=AppConfigType.PUBLISHED,
            **draft_app_config_copy,
        )

        return app

    def cancel_publish_app_config(self, app_id: UUID, account: Account) -> App:
        """Cancel publication of the specified application's configuration"""
        # 1. Get the app and validate permissions
        app = self.get_app(app_id, account)

        # 2. Check whether the app is published
        if app.status != AppStatus.PUBLISHED:
            raise FailException("The application has not been published, please verify and try again")

        # 3. Set app status back to DRAFT and clear runtime config ID
        self.update(app, status=AppStatus.DRAFT, app_config_id=None)

        # 4. Delete knowledge base associations for this app
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
        """Get the paginated list of published configuration history for the specified application"""
        # 1. Validate app and permissions
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
        """Fallback a specific historical configuration version to the draft configuration"""
        # 1. Validate app and permissions
        app = self.get_app(app_id, account)

        # 2. Query the specified historical configuration version
        app_config_version = self.get(AppConfigVersion, app_config_version_id)
        if not app_config_version:
            raise NotFoundException(
                "The specified historical configuration version does not exist, please verify and try again")

        # 3. Clean the historical config (remove deleted tools, datasets, workflows)
        draft_app_config_dict = app_config_version.__dict__.copy()
        remove_fields = ["id", "app_id", "version", "config_type", "updated_at", "created_at", "_sa_instance_state"]
        for field in remove_fields:
            draft_app_config_dict.pop(field)

        # 4. Validate the historical configuration
        draft_app_config_dict = self._validate_draft_app_config(draft_app_config_dict, account)

        # 5. Update the draft configuration
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            # todo: Patch to update the timestamp
            updated_at=datetime.now(),
            **draft_app_config_dict,
        )

        return draft_app_config_record

    def get_debug_conversation_summary(self, app_id: UUID, account: Account) -> str:
        """Get the long-term memory (summary) of the debug conversation for the specified application"""
        # 1. Validate app and permissions
        app = self.get_app(app_id, account)

        # 2. Get the draft config and check whether long-term memory is enabled
        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("Long-term memory is not enabled for this application")

        return app.debug_conversation.summary

    def update_debug_conversation_summary(self, app_id: UUID, summary: str, account: Account) -> Conversation:
        """Update the long-term memory (summary) of the debug conversation for the specified application"""
        # 1. Validate app and permissions
        app = self.get_app(app_id, account)

        # 2. Get the draft config and check whether long-term memory is enabled
        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("Long-term memory is not enabled for this application")

        # 3. Update long-term memory for the debug conversation
        debug_conversation = app.debug_conversation
        self.update(debug_conversation, summary=summary)

        return debug_conversation

    def delete_debug_conversation(self, app_id: UUID, account: Account) -> App:
        """Delete the debug conversation of the specified application"""
        # 1. Validate app and permissions
        app = self.get_app(app_id, account)

        # 2. If debug_conversation_id is not set, nothing to do
        if not app.debug_conversation_id:
            return app

        # 3. Otherwise, reset debug_conversation_id to None
        self.update(app, debug_conversation_id=None)

        return app

    def debug_chat(self, app_id: UUID, query: str, account: Account) -> Generator:
        """Trigger a debug conversation for the specified application using the given query"""
        # 1. Validate app and permissions
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

        # todo: 5. Instantiate different LLM models based on model_config.
        #       This will change once multi-LLM support is added.
        llm = ChatOpenAI(
            model=draft_app_config["model_config"]["model"],
            **draft_app_config["model_config"]["parameters"],
        )

        # 6. Initialize TokenBufferMemory for short-term memory extraction
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=debug_conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=draft_app_config["dialog_round"],
        )

        # 7. Convert tools in the draft config to LangChain tools
        tools = self.app_config_service.get_langchain_tools_by_tools_config(draft_app_config["tools"])

        # 8. Check whether there are associated datasets
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

        # todo: 10. Build the Agent. Currently we use FunctionCallAgent.
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
            # 11. Extract event ID
            event_id = str(agent_thought.id)

            # 12. Fill agent_thoughts, preparing to store to DB
            if agent_thought.event != QueueEvent.PING:
                # 13. For AGENT_MESSAGE, we accumulate content; otherwise we overwrite
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    if event_id not in agent_thoughts:
                        # 14. Initialize the agent message event
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 15. Accumulate the agent's message content
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

        # 22. Persist the message and reasoning process in a separate thread
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
        """Stop a debug conversation for the specified app and task"""
        # 1. Validate app and permissions
        self.get_app(app_id, account)

        # 2. Use AgentQueueManager to stop the specific task
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.DEBUGGER, account.id)

    def get_debug_conversation_messages_with_page(
            self,
            app_id: UUID,
            req: GetDebugConversationMessagesWithPageReq,
            account: Account
    ) -> tuple[list[Message], Paginator]:
        """Get paginated debug conversation messages for the specified application"""
        # 1. Validate app and permissions
        app = self.get_app(app_id, account)

        # 2. Get the app's debug conversation
        debug_conversation = app.debug_conversation

        # 3. Build paginator and filter conditions
        paginator = Paginator(db=self.db, req=req)
        filters = []
        if req.created_at.data:
            # 4. Convert timestamp to DateTime
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
        """Validate the given draft application configuration and return the validated data"""
        # 1. Check that the draft config contains at least one acceptable field
        acceptable_fields = [
            "model_config", "dialog_round", "preset_prompt",
            "tools", "workflows", "datasets", "retrieval_config",
            "long_term_memory", "opening_statement", "opening_questions",
            "speech_to_text", "text_to_speech", "suggested_after_answer", "review_config",
        ]

        # 2. Ensure all fields are within the acceptable set
        if (
                not draft_app_config
                or not isinstance(draft_app_config, dict)
                or set(draft_app_config.keys()) - set(acceptable_fields)
        ):
            raise ValidateErrorException("Invalid draft configuration fields, please verify and try again")

        # todo: 3. Validate model_config when multi-LLM support is added

        # 4. Validate dialog_round (context rounds), including type and range
        if "dialog_round" in draft_app_config:
            dialog_round = draft_app_config["dialog_round"]
            if not isinstance(dialog_round, int) or not (0 <= dialog_round <= 100):
                raise ValidateErrorException("The context round count must be an integer in the range 0–100")

        # 5. Validate preset_prompt
        if "preset_prompt" in draft_app_config:
            preset_prompt = draft_app_config["preset_prompt"]
            if not isinstance(preset_prompt, str) or len(preset_prompt) > 2000:
                raise ValidateErrorException(
                    "Preset prompt must be a string with length in the range 0–2000 characters")

        # 6. Validate tools
        if "tools" in draft_app_config:
            tools = draft_app_config["tools"]
            validate_tools = []

            # 6.1 tools must be a list; an empty list means no tools are bound
            if not isinstance(tools, list):
                raise ValidateErrorException("The tool list must be a list")
            # 6.2 Length of tools must not exceed 5
            if len(tools) > 5:
                raise ValidateErrorException("An Agent cannot bind more than 5 tools")
            # 6.3 Validate each tool
            for tool in tools:
                # 6.4 Tool must be non-empty and of type dict
                if not tool or not isinstance(tool, dict):
                    raise ValidateErrorException("Invalid tool binding parameters")
                # 6.5 The keys must be exactly {type, provider_id, tool_id, params}
                if set(tool.keys()) != {"type", "provider_id", "tool_id", "params"}:
                    raise ValidateErrorException("Invalid tool binding parameters")
                # 6.6 type must be either builtin_tool or api_tool
                if tool["type"] not in ["builtin_tool", "api_tool"]:
                    raise ValidateErrorException("Invalid tool type in tool binding parameters")
                # 6.7 Validate provider_id and tool_id
                if (
                        not tool["provider_id"]
                        or not tool["tool_id"]
                        or not isinstance(tool["provider_id"], str)
                        or not isinstance(tool["tool_id"], str)
                ):
                    raise ValidateErrorException("Invalid provider or tool identifier in tool binding parameters")
                # 6.8 Validate params, which must be a dict
                if not isinstance(tool["params"], dict):
                    raise ValidateErrorException("Custom tool parameter format is incorrect")
                # 6.9 Check whether the tool actually exists, split into builtin_tool and api_tool
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

            # 6.10 Check whether tools are duplicated
            check_tools = [f"{tool['provider_id']}_{tool['tool_id']}" for tool in validate_tools]
            if len(set(check_tools)) != len(validate_tools):
                raise ValidateErrorException("Duplicate tools detected in tool bindings")

            # 6.11 Reassign validated tools
            draft_app_config["tools"] = validate_tools

        # todo: 7. Validate workflows once the workflow module is completed
        if "workflows" in draft_app_config:
            draft_app_config["workflows"] = []

        # 8. Validate datasets (knowledge base list)
        if "datasets" in draft_app_config:
            datasets = draft_app_config["datasets"]

            # 8.1 datasets must be a list
            if not isinstance(datasets, list):
                raise ValidateErrorException("Knowledge base list parameter format is incorrect")
            # 8.2 Number of datasets must not exceed 5
            if len(datasets) > 5:
                raise ValidateErrorException("An Agent cannot bind more than 5 knowledge bases")
            # 8.3 Validate each dataset parameter
            for dataset_id in datasets:
                try:
                    UUID(dataset_id)
                except Exception:
                    raise ValidateErrorException("Each knowledge base identifier must be a valid UUID")
            # 8.4 Check for duplicates
            if len(set(datasets)) != len(datasets):
                raise ValidateErrorException("Duplicate knowledge bases detected in bindings")
            # 8.5 Validate dataset permissions and remove datasets not owned by the current account
            dataset_records = self.db.session.query(Dataset).filter(
                Dataset.id.in_(datasets),
                Dataset.account_id == account.id,
            ).all()
            dataset_sets = set([str(dataset_record.id) for dataset_record in dataset_records])
            draft_app_config["datasets"] = [dataset_id for dataset_id in datasets if dataset_id in dataset_sets]

        # 9. Validate retrieval_config
        if "retrieval_config" in draft_app_config:
            retrieval_config = draft_app_config["retrieval_config"]

            # 9.1 Must be non-empty dict
            if not retrieval_config or not isinstance(retrieval_config, dict):
                raise ValidateErrorException("Retrieval configuration format is incorrect")
            # 9.2 Validate field set
            if set(retrieval_config.keys()) != {"retrieval_strategy", "k", "score"}:
                raise ValidateErrorException("Retrieval configuration format is incorrect")
            # 9.3 Validate retrieval_strategy
            if retrieval_config["retrieval_strategy"] not in ["semantic", "full_text", "hybrid"]:
                raise ValidateErrorException("Retrieval strategy format is incorrect")
            # 9.4 Validate max recall number k
            if not isinstance(retrieval_config["k"], int) or not (0 <= retrieval_config["k"] <= 10):
                raise ValidateErrorException(
                    "The maximum number of retrieved items must be an integer in the range 0–10")
            # 9.5 Validate score / minimum similarity
            if not isinstance(retrieval_config["score"], float) or not (0 <= retrieval_config["score"] <= 1):
                raise ValidateErrorException("The minimum relevance score must be a float in the range 0–1")

        # 10. Validate long_term_memory configuration
        if "long_term_memory" in draft_app_config:
            long_term_memory = draft_app_config["long_term_memory"]

            # 10.1 Check format
            if not long_term_memory or not isinstance(long_term_memory, dict):
                raise ValidateErrorException("Long-term memory configuration format is incorrect")
            # 10.2 Check properties
            if (
                    set(long_term_memory.keys()) != {"enable"}
                    or not isinstance(long_term_memory["enable"], bool)
            ):
                raise ValidateErrorException("Long-term memory configuration format is incorrect")

        # 11. Validate opening_statement
        if "opening_statement" in draft_app_config:
            opening_statement = draft_app_config["opening_statement"]

            # 11.1 Check type and length
            if not isinstance(opening_statement, str) or len(opening_statement) > 2000:
                raise ValidateErrorException("Opening statement length must be in the range 0–2000")

        # 12. Validate opening_questions
        if "opening_questions" in draft_app_config:
            opening_questions = draft_app_config["opening_questions"]

            # 12.1 Must be a list with length <= 3
            if not isinstance(opening_questions, list) or len(opening_questions) > 3:
                raise ValidateErrorException("There can be at most 3 opening questions")
            # 12.2 Each opening question must be a string
            for opening_question in opening_questions:
                if not isinstance(opening_question, str):
                    raise ValidateErrorException("Each opening question must be a string")

        # 13. Validate speech_to_text
        if "speech_to_text" in draft_app_config:
            speech_to_text = draft_app_config["speech_to_text"]

            # 13.1 Check format
            if not speech_to_text or not isinstance(speech_to_text, dict):
                raise ValidateErrorException("Speech-to-text configuration format is incorrect")
            # 13.2 Check properties
            if (
                    set(speech_to_text.keys()) != {"enable"}
                    or not isinstance(speech_to_text["enable"], bool)
            ):
                raise ValidateErrorException("Speech-to-text configuration format is incorrect")

        # 14. Validate text_to_speech
        if "text_to_speech" in draft_app_config:
            text_to_speech = draft_app_config["text_to_speech"]

            # 14.1 Must be a dict
            if not isinstance(text_to_speech, dict):
                raise ValidateErrorException("Text-to-speech configuration format is incorrect")
            # 14.2 Validate fields and types
            if (
                    set(text_to_speech.keys()) != {"enable", "voice", "auto_play"}
                    or not isinstance(text_to_speech["enable"], bool)
                    # todo: Add more voices once multi-modal Agent support is implemented
                    or text_to_speech["voice"] not in ["echo"]
                    or not isinstance(text_to_speech["auto_play"], bool)
            ):
                raise ValidateErrorException("Text-to-speech configuration format is incorrect")

        # 15. Validate suggested_after_answer
        if "suggested_after_answer" in draft_app_config:
            suggested_after_answer = draft_app_config["suggested_after_answer"]

            # 15.1 Check format
            if not suggested_after_answer or not isinstance(suggested_after_answer, dict):
                raise ValidateErrorException("Suggested-questions-after-answer configuration format is incorrect")
            # 15.2 Check fields
            if (
                    set(suggested_after_answer.keys()) != {"enable"}
                    or not isinstance(suggested_after_answer["enable"], bool)
            ):
                raise ValidateErrorException("Suggested-questions-after-answer configuration format is incorrect")

        # 16. Validate review_config (content moderation / review config)
        if "review_config" in draft_app_config:
            review_config = draft_app_config["review_config"]

            # 16.1 Must be a non-empty dict
            if not review_config or not isinstance(review_config, dict):
                raise ValidateErrorException("Review configuration format is incorrect")
            # 16.2 Validate field set
            if set(review_config.keys()) != {"enable", "keywords", "inputs_config", "outputs_config"}:
                raise ValidateErrorException("Review configuration format is incorrect")
            # 16.3 Validate enable
            if not isinstance(review_config["enable"], bool):
                raise ValidateErrorException("review.enable must be a boolean")
            # 16.4 Validate keywords
            if (
                    not isinstance(review_config["keywords"], list)
                    or (review_config["enable"] and len(review_config["keywords"]) == 0)
                    or len(review_config["keywords"]) > 100
            ):
                raise ValidateErrorException(
                    "review.keywords must be a non-empty list (when enabled) and contain at most 100 keywords")
            for keyword in review_config["keywords"]:
                if not isinstance(keyword, str):
                    raise ValidateErrorException("Each review.keyword must be a string")
            # 16.5 Validate inputs_config
            if (
                    not review_config["inputs_config"]
                    or not isinstance(review_config["inputs_config"], dict)
                    or set(review_config["inputs_config"].keys()) != {"enable", "preset_response"}
                    or not isinstance(review_config["inputs_config"]["enable"], bool)
                    or not isinstance(review_config["inputs_config"]["preset_response"], str)
            ):
                raise ValidateErrorException("review.inputs_config must be a dict with valid fields")
            # 16.6 Validate outputs_config
