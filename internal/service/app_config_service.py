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

from internal.core.language_model import LanguageModelManager
from internal.core.tools.api_tools.entities import ToolEntity
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.entity.app_entity import DEFAULT_APP_CONFIG
from internal.lib.helper import datetime_to_timestamp, get_value_type
from internal.model import App, ApiTool, Dataset, AppConfig, AppConfigVersion, AppDatasetJoin
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from ..core.language_model.entities.model_entity import ModelParameterType


@inject
@dataclass
class AppConfigService(BaseService):
    """Application configuration service"""
    db: SQLAlchemy
    api_provider_manager: ApiProviderManager
    builtin_provider_manager: BuiltinProviderManager
    language_model_manager: LanguageModelManager

    def get_draft_app_config(self, app: App) -> dict[str, Any]:
        """Get the draft configuration for the given app"""
        # 1. Get draft configuration of the app
        draft_app_config = app.draft_app_config

        validate_model_config = self._process_and_validate_model_config(draft_app_config.model_config)
        if draft_app_config.model_config != validate_model_config:
            self.update(draft_app_config, model_config=validate_model_config)

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

        # 2. Validate Model Config
        validate_model_config = self._process_and_validate_model_config(app_config.model_config)
        if app_config.model_config != validate_model_config:
            self.update(app_config, model_config=validate_model_config)

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

    def _process_and_validate_model_config(self, origin_model_config: dict[str, Any]) -> dict[str, Any]:
        """Process and validate the given model configuration, then return the validated config."""
        # 1. Check whether origin_model_config is a dict; if not, return the default config
        if not isinstance(origin_model_config, dict):
            return DEFAULT_APP_CONFIG["model_config"]

        # 2. Extract provider, model, and parameters from origin_model_config
        model_config = {
            "provider": origin_model_config.get("provider", ""),
            "model": origin_model_config.get("model", ""),
            "parameters": origin_model_config.get("parameters", {}),
        }

        # 3. Validate provider existence and type; if invalid, return default config
        if not model_config["provider"] or not isinstance(model_config["provider"], str):
            return DEFAULT_APP_CONFIG["model_config"]
        provider = self.language_model_manager.get_provider(model_config["provider"])
        if not provider:
            return DEFAULT_APP_CONFIG["model_config"]

        # 4. Validate model existence and type; if invalid, return default config
        if not model_config["model"] or not isinstance(model_config["model"], str):
            return DEFAULT_APP_CONFIG["model_config"]
        model_entity = provider.get_model_entity(model_config["model"])
        if not model_entity:
            return DEFAULT_APP_CONFIG["model_config"]

        # 5. Validate parameters type; if invalid, initialize with default values
        if not isinstance(model_config["parameters"], dict):
            model_config["parameters"] = {
                parameter.name: parameter.default for parameter in model_entity.parameters
            }

        # 6. Remove extra parameters and fill in missing ones with defaults
        parameters = {}
        for parameter in model_entity.parameters:
            # 7. Get parameter value from model_config; if not present, use default
            parameter_value = model_config["parameters"].get(parameter.name, parameter.default)

            # 8. Check whether the parameter is required
            if parameter.required:
                # 9. Required parameters must not be None; if None, use default value
                if parameter_value is None:
                    parameter_value = parameter.default
                else:
                    # 10. If non-None, validate type; if type is incorrect, use default value
                    if get_value_type(parameter_value) != parameter.type.value:
                        parameter_value = parameter.default
            else:
                # 11. For optional parameters, validate type only when non-None
                if parameter_value is not None:
                    if get_value_type(parameter_value) != parameter.type.value:
                        parameter_value = parameter.default

            # 12. If the parameter has options, the value must be one of them
            if parameter.options and parameter_value not in parameter.options:
                parameter_value = parameter.default

            # 13. For int/float parameters with min/max, validate numeric range
            if parameter.type in [ModelParameterType.INT, ModelParameterType.FLOAT] and parameter_value is not None:
                # 14. Validate min/max bounds
                if (
                        (parameter.min and parameter_value < parameter.min)
                        or (parameter.max and parameter_value > parameter.max)
                ):
                    parameter_value = parameter.default

            parameters[parameter.name] = parameter_value

        # 15. After validation, assign the normalized parameters back
        model_config["parameters"] = parameters

        return model_config
