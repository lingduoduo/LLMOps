#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : app_config_service.py
"""
from dataclasses import dataclass
from typing import Any, Union
from uuid import UUID

from flask import request
from injector import inject
from langchain_core.tools import BaseTool

from internal.core.language_model import LanguageModelManager
from internal.core.language_model.entities.model_entity import ModelParameterType
from internal.core.tools.api_tools.entities import ToolEntity
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.core.workflow import Workflow as WorkflowTool
from internal.entity.app_entity import DEFAULT_APP_CONFIG
from internal.entity.workflow_entity import WorkflowStatus
from internal.lib.helper import datetime_to_timestamp, get_value_type
from internal.model import (
    App,
    ApiTool,
    Dataset,
    AppConfig,
    AppConfigVersion,
    AppDatasetJoin,
    Workflow,
)
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from ..core.workflow.entities.workflow_entity import WorkflowConfig


@inject
@dataclass
class AppConfigService(BaseService):
    """Application configuration service."""
    db: SQLAlchemy
    api_provider_manager: ApiProviderManager
    builtin_provider_manager: BuiltinProviderManager
    language_model_manager: LanguageModelManager

    def get_draft_app_config(self, app: App) -> dict[str, Any]:
        """Get the draft configuration for the given app."""
        # 1. Extract the app's draft configuration
        draft_app_config = app.draft_app_config

        # 2. Validate model_config; if it uses a non-existent provider/model,
        #    fall back to the default value (lenient validation).
        validate_model_config = self._process_and_validate_model_config(draft_app_config.model_config)
        if draft_app_config.model_config != validate_model_config:
            self.update(draft_app_config, model_config=validate_model_config)

        # 3. Iterate through the tools list and drop tools that no longer exist
        tools, validate_tools = self._process_and_validate_tools(draft_app_config.tools)

        # 4. Check whether the draft config's tools list needs to be updated
        if draft_app_config.tools != validate_tools:
            # 4.1 Update the tools list in the draft configuration
            self.update(draft_app_config, tools=validate_tools)

        # 5. Validate the dataset list: if it references non-existent / deleted datasets,
        #    filter them out and update, and at the same time fetch extra dataset metadata.
        datasets, validate_datasets = self._process_and_validate_datasets(draft_app_config.datasets)

        # 6. If there are deleted datasets, update the draft configuration
        if set(validate_datasets) != set(draft_app_config.datasets):
            self.update(draft_app_config, datasets=validate_datasets)

        # 7. Validate the workflow list and corresponding data
        workflows, validate_workflows = self._process_and_validate_workflows(draft_app_config.workflows)
        if set(validate_workflows) != set(draft_app_config.workflows):
            self.update(draft_app_config, workflows=validate_workflows)

        # 8. Transform everything into a dictionary and return
        return self._process_and_transformer_app_config(
            validate_model_config,
            tools,
            workflows,
            datasets,
            draft_app_config,
        )

    def get_app_config(self, app: App) -> dict[str, Any]:
        """Get the runtime configuration for the given app."""
        # 1. Extract the app's runtime configuration
        app_config = app.app_config

        # 2. Validate model_config; if model_config in the runtime config has changed,
        #    update it.
        validate_model_config = self._process_and_validate_model_config(app_config.model_config)
        if app_config.model_config != validate_model_config:
            self.update(app_config, model_config=validate_model_config)

        # 3. Iterate through the tools list and drop tools that no longer exist
        tools, validate_tools = self._process_and_validate_tools(app_config.tools)

        # 4. Check whether the runtime config's tools list needs to be updated
        if app_config.tools != validate_tools:
            # 4.1 Update the tools list in the runtime configuration
            self.update(app_config, tools=validate_tools)

        # 5. Validate the dataset list: if it references non-existent / deleted datasets,
        #    filter them out and update, and at the same time fetch extra dataset metadata.
        app_dataset_joins = app_config.app_dataset_joins
        origin_datasets = [str(app_dataset_join.dataset_id) for app_dataset_join in app_dataset_joins]
        datasets, validate_datasets = self._process_and_validate_datasets(origin_datasets)

        # 6. If there are deleted datasets, remove the corresponding AppDatasetJoin records
        for dataset_id in (set(origin_datasets) - set(validate_datasets)):
            with self.db.auto_commit():
                self.db.session.query(AppDatasetJoin).filter(
                    AppDatasetJoin.dataset_id == dataset_id
                ).delete()

        # 7. Validate the workflow list and corresponding data
        workflows, validate_workflows = self._process_and_validate_workflows(app_config.workflows)
        if set(validate_workflows) != set(app_config.workflows):
            self.update(app_config, workflows=validate_workflows)

        # 8. Transform everything into a dictionary and return
        return self._process_and_transformer_app_config(
            validate_model_config,
            tools,
            workflows,
            datasets,
            app_config,
        )

    def get_langchain_tools_by_tools_config(self, tools_config: list[dict]) -> list[BaseTool]:
        """Build a list of LangChain tools from the given tool configuration list."""
        # 1. Iterate over all tool configs
        tools: list[BaseTool] = []
        for tool in tools_config:
            # 2. Handle different tool types
            if tool["type"] == "builtin_tool":
                # 3. Built-in tools: obtain an instance via builtin_provider_manager
                builtin_tool = self.builtin_provider_manager.get_tool(
                    tool["provider"]["id"],
                    tool["tool"]["name"],
                )
                if not builtin_tool:
                    continue
                tools.append(builtin_tool(**tool["tool"]["params"]))
            else:
                # 4. API tools: first look up the ApiTool record by id, then create an instance
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

    def get_langchain_tools_by_workflow_ids(self, workflow_ids: list[UUID]) -> list[BaseTool]:
        """Build a list of LangChain tools from the given workflow ID list."""
        # 1. Query workflow records by the given workflow IDs
        workflow_records = self.db.session.query(Workflow).filter(
            Workflow.id.in_(workflow_ids),
            Workflow.status == WorkflowStatus.PUBLISHED,
        ).all()

        # 2. Iterate over all workflow records
        workflows: list[BaseTool] = []
        for workflow_record in workflow_records:
            try:
                # 3. Create workflow tools
                workflow_tool = WorkflowTool(
                    workflow_config=WorkflowConfig(
                        account_id=workflow_record.account_id,
                        name=f"wf_{workflow_record.tool_call_name}",
                        description=workflow_record.description,
                        nodes=workflow_record.graph.get("nodes", []),
                        edges=workflow_record.graph.get("edges", []),
                    )
                )
                workflows.append(workflow_tool)
            except Exception:
                # If the workflow cannot be instantiated, skip it
                continue

        return workflows

    @classmethod
    def _process_and_transformer_app_config(
            cls,
            model_config: dict[str, Any],
            tools: list[dict],
            workflows: list[dict],
            datasets: list[dict],
            app_config: Union[AppConfig, AppConfigVersion],
    ) -> dict[str, Any]:
        """
        Build a configuration dictionary from the given model config, tool list,
        workflow list, dataset list, and app configuration object.
        """
        return {
            "id": str(app_config.id),
            "model_config": model_config,
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
        """
        Process and validate the given raw tool list, returning:
        - tools: the list of enriched tool info for display
        - validate_tools: the cleaned tool configuration to persist
        """
        # 1. Iterate through the tool list and drop tools that have been deleted
        validate_tools: list[dict] = []
        tools: list[dict] = []

        for tool in origin_tools:
            if tool["type"] == "builtin_tool":
                # 2. Look up the built-in tool provider and check that it exists
                provider = self.builtin_provider_manager.get_provider(tool["provider_id"])
                if not provider:
                    continue

                # 3. Get the tool entity under that provider and check that it exists
                tool_entity = provider.get_tool_entity(tool["tool_id"])
                if not tool_entity:
                    continue

                # 4. Check whether the params in the config match the tool's params.
                #    If they don't match, reset params to the default values
                #    (or alternatively, remove the tool reference altogether).
                param_keys = {param.name for param in tool_entity.params}
                params = tool["params"]
                if set(tool["params"].keys()) - param_keys:
                    params = {
                        param.name: param.default
                        for param in tool_entity.params
                        if param.default is not None
                    }

                # 5. All data exists and parameters are validated; add to validate_tools
                validate_tools.append({**tool, "params": params})

                # 6. Build enriched display info for the built-in tool
                provider_entity = provider.provider_entity
                tools.append(
                    {
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
                        },
                    }
                )

            elif tool["type"] == "api_tool":
                # 7. Look up the corresponding API tool record and check that it exists
                tool_record = self.db.session.query(ApiTool).filter(
                    ApiTool.provider_id == tool["provider_id"],
                    ApiTool.name == tool["tool_id"],
                ).one_or_none()
                if not tool_record:
                    continue

                # 8. Validation passed; add to validate_tools
                validate_tools.append(tool)

                # 9. Build enriched display info for the API tool
                provider = tool_record.provider
                tools.append(
                    {
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
                    }
                )

        return tools, validate_tools

    def _process_and_validate_datasets(self, origin_datasets: list[dict]) -> tuple[list[dict], list[dict]]:
        """
        Process the given dataset list and return:
        - datasets: enriched dataset configs
        - validate_datasets: validated dataset IDs
        """
        # 1. Validate the dataset list. If it references non-existent / deleted datasets,
        #    filter them out and update, and at the same time fetch extra dataset metadata.
        datasets: list[dict] = []
        dataset_records = self.db.session.query(Dataset).filter(
            Dataset.id.in_(origin_datasets)
        ).all()
        dataset_dict = {str(dataset_record.id): dataset_record for dataset_record in dataset_records}
        dataset_sets = set(dataset_dict.keys())

        # 2. Compute the list of existing dataset IDs.
        #    To preserve the original order, use a list comprehension.
        validate_datasets = [dataset_id for dataset_id in origin_datasets if dataset_id in dataset_sets]

        # 3. Build dataset data for each valid dataset
        for dataset_id in validate_datasets:
            dataset = dataset_dict.get(str(dataset_id))
            datasets.append(
                {
                    "id": str(dataset.id),
                    "name": dataset.name,
                    "icon": dataset.icon,
                    "description": dataset.description,
                }
            )

        return datasets, validate_datasets

    def _process_and_validate_model_config(self, origin_model_config: dict[str, Any]) -> dict[str, Any]:
        """
        Process and validate the given model configuration, then return the validated config.
        """
        # 1. model_config must be a dict; otherwise, fall back to the default config
        if not isinstance(origin_model_config, dict):
            return DEFAULT_APP_CONFIG["model_config"]

        # 2. Extract provider, model, and parameters from origin_model_config
        model_config = {
            "provider": origin_model_config.get("provider", ""),
            "model": origin_model_config.get("model", ""),
            "parameters": origin_model_config.get("parameters", {}),
        }

        # 3. Validate provider: must exist and be a string; otherwise use the default config
        if not model_config["provider"] or not isinstance(model_config["provider"], str):
            return DEFAULT_APP_CONFIG["model_config"]
        provider = self.language_model_manager.get_provider(model_config["provider"])
        if not provider:
            return DEFAULT_APP_CONFIG["model_config"]

        # 4. Validate model: must exist and be a string; otherwise use the default config
        if not model_config["model"] or not isinstance(model_config["model"], str):
            return DEFAULT_APP_CONFIG["model_config"]
        model_entity = provider.get_model_entity(model_config["model"])
        if not model_entity:
            return DEFAULT_APP_CONFIG["model_config"]

        # 5. If parameters is not a dict, reset it to the default values
        if not isinstance(model_config["parameters"], dict):
            model_config["parameters"] = {
                parameter.name: parameter.default for parameter in model_entity.parameters
            }

        # 6. Remove extra parameters and fill missing ones with default values
        parameters: dict[str, Any] = {}
        for parameter in model_entity.parameters:
            # 7. Get the parameter value from model_config or fall back to the default
            parameter_value = model_config["parameters"].get(parameter.name, parameter.default)

            # 8. Check whether the parameter is required
            if parameter.required:
                # 9. Required parameters cannot be None; if None, use the default
                if parameter_value is None:
                    parameter_value = parameter.default
                else:
                    # 10. For non-empty values, validate the data type; if incorrect, use the default
                    if get_value_type(parameter_value) != parameter.type.value:
                        parameter_value = parameter.default
            else:
                # 11. For optional parameters, validate the type only when non-empty
                if parameter_value is not None:
                    if get_value_type(parameter_value) != parameter.type.value:
                        parameter_value = parameter.default

            # 12. If the parameter has options, its value must be within the options
            if parameter.options and parameter_value not in parameter.options:
                parameter_value = parameter.default

            # 13. For int/float parameters, if min/max are set, validate the range
            if (
                    parameter.type in [ModelParameterType.INT, ModelParameterType.FLOAT]
                    and parameter_value is not None
            ):
                # 14. Validate min/max bounds
                if ((parameter.min and parameter_value < parameter.min) or
                        (parameter.max and parameter_value > parameter.max)):
                    parameter_value = parameter.default

            parameters[parameter.name] = parameter_value

        # 15. Assign the validated parameter dictionary back to model_config
        model_config["parameters"] = parameters

        return model_config

    def _process_and_validate_workflows(self, origin_workflows: list[UUID]) -> tuple[list[dict], list[UUID]]:
        """
        Process the given workflow ID list and return:
        - workflows: enriched workflow configs
        - validate_workflows: validated workflow IDs
        """
        # 1. Validate the workflow config list. If it references non-existent / deleted workflows,
        #    filter them out and update, and at the same time fetch extra workflow metadata.
        workflows: list[dict] = []
        workflow_records = self.db.session.query(Workflow).filter(
            Workflow.id.in_(origin_workflows),
            Workflow.status == WorkflowStatus.PUBLISHED,
        ).all()
        workflow_dict = {str(workflow_record.id): workflow_record for workflow_record in workflow_records}
        workflow_sets = set(workflow_dict.keys())

        # 2. Compute the list of existing workflow IDs.
        #    To preserve the original order, use a list comprehension.
        #    Note: origin_workflows are UUID objects, while workflow_sets contains string IDs,
        #    so we cast to str for the membership check.
        validate_workflows = [
            workflow_id for workflow_id in origin_workflows if str(workflow_id) in workflow_sets
        ]

        # 3. Build workflow data for each valid workflow
        for workflow_id in validate_workflows:
            workflow = workflow_dict.get(str(workflow_id))
            workflows.append(
                {
                    "id": str(workflow.id),
                    "name": workflow.name,
                    "icon": workflow.icon,
                    "description": workflow.description,
                }
            )

        return workflows, validate_workflows
