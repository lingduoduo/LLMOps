#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : app_config_service.py
"""
from dataclasses import dataclass
from typing import Any, Union

from flask import request
from injector import inject
from langchain_core.tools import BaseTool

from internal.core.tools.api_tools.entities import ToolEntity
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.lib.helper import datetime_to_timestamp
from internal.model import App, ApiTool, Dataset, AppConfig, AppConfigVersion, AppDatasetJoin
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class AppConfigService(BaseService):
    """Application configuration service"""
    db: SQLAlchemy
    api_provider_manager: ApiProviderManager
    builtin_provider_manager: BuiltinProviderManager

    def get_draft_app_config(self, app: App) -> dict[str, Any]:
        """Get the draft configuration for the given app"""
        # 1. Get draft configuration of the app
        draft_app_config = app.draft_app_config

        # TODO: 2. Validate model_config; to be completed when multi-LLM support is added

        # 3. Iterate over tools and remove those that no longer exist
        tools, validate_tools = self._process_and_validate_tools(draft_app_config.tools)

        # 4. Update tool list in draft config if needed
        if draft_app_config.tools != validate_tools:
            # 14. Update tools in draft app config
            self.update(draft_app_config, tools=validate_tools)

        # 5. Validate dataset list: if it references deleted/non-existent datasets,
        #    remove them and update, while also fetching dataset metadata
        datasets, validate_datasets = self._process_and_validate_datasets(draft_app_config.datasets)

        # 6. If there are deleted datasets, update the config
        if set(validate_datasets) != set(draft_app_config.datasets):
            self.update(draft_app_config, datasets=validate_datasets)

        # TODO: 7. Validate workflow configuration
        workflows = []

        # 20. Transform into a dict and return
        return self._process_and_transformer_app_config(tools, workflows, datasets, draft_app_config)

    def get_app_config(self, app: App) -> dict[str, Any]:
        """Get the runtime configuration for the given app"""
        # 1. Get runtime app configuration
        app_config = app.app_config

        # TODO: 2. Validate model_config; to be completed when multi-LLM support is added

        # 3. Iterate over tools and remove those that no longer exist
        tools, validate_tools = self._process_and_validate_tools(app_config.tools)

        # 4. Update tool list if needed
        if app_config.tools != validate_tools:
            # 14. Update tools in app config
            self.update(app_config, tools=validate_tools)

        # 5. Validate dataset list: remove deleted/non-existent datasets and also fetch dataset metadata
        app_dataset_joins = app_config.app_dataset_joins
        origin_datasets = [str(app_dataset_join.dataset_id) for app_dataset_join in app_dataset_joins]
        datasets, validate_datasets = self._process_and_validate_datasets(origin_datasets)

        # 6. If there are deleted datasets, update join table
        for dataset_id in (set(origin_datasets) - set(validate_datasets)):
            with self.db.auto_commit():
                self.db.session.query(AppDatasetJoin).filter(AppDatasetJoin.dataset_id == dataset_id).delete()

        # TODO: 7. Validate workflow configuration
        workflows = []

        # 20. Transform into a dict and return
        return self._process_and_transformer_app_config(tools, workflows, datasets, app_config)

    def get_langchain_tools_by_tools_config(self, tools_config: list[dict]) -> list[BaseTool]:
        """Build a list of LangChain tools from the given tools configuration"""
        # 1. Iterate over all tool configs
        tools = []
        for tool in tools_config:
            # 2. Handle different tool types
            if tool["type"] == "builtin_tool":
                # 3. Built-in tool: get tool instance via builtin_provider_manager
                builtin_tool = self.builtin_provider_manager.get_tool(
                    tool["provider"]["id"],
                    tool["tool"]["name"]
                )
                if not builtin_tool:
                    continue
                tools.append(builtin_tool(**tool["tool"]["params"]))
            else:
                # 4. API tool: fetch ApiTool record first, then create instance
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

        return tools

    @classmethod
    def _process_and_transformer_app_config(
            cls,
            tools: list[dict],
            workflows: list[dict],
            datasets: list[dict],
            app_config: Union[AppConfig, AppConfigVersion]
    ) -> dict[str, Any]:
        """Build the app configuration dictionary from tools, workflows, datasets, and app_config"""
        return {
            "id": str(app_config.id),
            "model_config": app_config.model_config,
            "dialog_round": app_config.dialog_round,
            "preset_prompt": app_config.preset_prompt,
            "tools": tools,
            "workflows": workflows,
            "datasets": datasets,
            "retrieval_config": app_config.retrieval_config,
            "long_term_memory": app_config.long_term_memory,
            "opening_statement": app_config.opening_statement,
            "opening_questions": app_config.opening_questions,
            "speech_to_text": app_config.speech_to_text,
            "text_to_speech": app_config.text_to_speech,
            "suggested_after_answer": app_config.suggested_after_answer,
            "review_config": app_config.review_config,
            "updated_at": datetime_to_timestamp(app_config.updated_at),
            "created_at": datetime_to_timestamp(app_config.created_at),
        }

    def _process_and_validate_tools(self, origin_tools: list[dict]) -> tuple[list[dict], list[dict]]:
        """Validate and normalize tool configuration list"""
        # 1. Iterate and remove tools that no longer exist
        validate_tools = []
        tools = []
        for tool in origin_tools:
            if tool["type"] == "builtin_tool":
                # 2. Fetch built-in tool provider and verify it exists
                provider = self.builtin_provider_manager.get_provider(tool["provider_id"])
                if not provider:
                    continue

                # 3. Get tool entity under that provider and verify it exists
                tool_entity = provider.get_tool_entity(tool["tool_id"])
                if not tool_entity:
                    continue

                # 4. Compare params with the tool entity definition; if mismatched, reset to defaults
                param_keys = set([param.name for param in tool_entity.params])
                params = tool["params"]
                if set(tool["params"].keys()) - param_keys:
                    params = {
                        param.name: param.default
                        for param in tool_entity.params
                        if param.default is not None
                    }

                # 5. After validation, add to validate_tools
                validate_tools.append({**tool, "params": params})

                # 6. Build display info for built-in tools
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
                        "params": tool["params"],
                    }
                })
            elif tool["type"] == "api_tool":
                # 7. Look up API tool record in DB and verify it exists
                tool_record = self.db.session.query(ApiTool).filter(
                    ApiTool.provider_id == tool["provider_id"],
                    ApiTool.name == tool["tool_id"],
                ).one_or_none()
                if not tool_record:
                    continue

                # 8. After validation, add to validate_tools
                validate_tools.append(tool)

                # 9. Build display info for API tools
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

        return tools, validate_tools

    def _process_and_validate_datasets(self, origin_datasets: list[dict]) -> tuple[list[dict], list[dict]]:
        """Validate dataset IDs and return dataset configs plus filtered IDs"""
        # 1. Validate dataset list; remove references to deleted/non-existent datasets
        #    and fetch additional dataset metadata
        datasets = []
        dataset_records = self.db.session.query(Dataset).filter(Dataset.id.in_(origin_datasets)).all()
        dataset_dict = {str(dataset_record.id): dataset_record for dataset_record in dataset_records}
        dataset_sets = set(dataset_dict.keys())

        # 2. Compute valid dataset IDs, preserving original order
        validate_datasets = [dataset_id for dataset_id in origin_datasets if dataset_id in dataset_sets]

        # 3. Build dataset metadata list
        for dataset_id in validate_datasets:
            dataset = dataset_dict.get(str(dataset_id))
            datasets.append({
                "id": str(dataset.id),
                "name": dataset.name,
                "icon": dataset.icon,
                "description": dataset.description,
            })

        return datasets, validate_datasets
