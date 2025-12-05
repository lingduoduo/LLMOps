#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : provider_entity.py
"""
import os.path
from typing import Union, Type, Any, Optional

import yaml
from langchain_core.pydantic_v1 import BaseModel, Field, root_validator

from internal.exception import FailException, NotFoundException
from internal.lib.helper import dynamic_import
from .default_model_parameter_template import DEFAULT_MODEL_PARAMETER_TEMPLATE
from .model_entity import ModelType, ModelEntity, BaseLanguageModel


class ProviderEntity(BaseModel):
    """Model provider metadata entity"""
    name: str = ""  # Provider name
    label: str = ""  # Provider label
    description: str = ""  # Provider description
    icon: str = ""  # Provider icon
    background: str = ""  # Provider icon background
    supported_model_types: list[ModelType] = Field(default_factory=list)  # Supported model types


class Provider(BaseModel):
    """
    Large Language Model (LLM) service provider.
    This class provides access to all model metadata, descriptions,
    icons, labels, and more under a given provider.
    """
    name: str  # Provider name
    position: int  # Provider ordering index
    provider_entity: ProviderEntity  # Provider metadata entity
    model_entity_map: dict[str, ModelEntity] = Field(default_factory=dict)  # Mapping of model name → ModelEntity
    model_class_map: dict[str, Union[None, Type[BaseLanguageModel]]] = Field(
        default_factory=dict)  # Mapping of model type → model class

    @root_validator(pre=False)
    def validate_provider(cls, provider: dict[str, Any]) -> dict[str, Any]:
        """
        Provider validator.
        This validator initializes provider model classes and model entities based on YAML files.
        """
        # 1. Retrieve provider metadata
        provider_entity: ProviderEntity = provider["provider_entity"]

        # 2. Dynamically import provider's model classes
        for model_type in provider_entity.supported_model_types:
            # 3. Capitalize the first character of the model type to construct class name
            symbol_name = model_type[0].upper() + model_type[1:]
            provider["model_class_map"][model_type] = dynamic_import(
                f"internal.core.language_model.providers.{provider_entity.name}.{model_type}",
                symbol_name
            )

        # 4. Construct path to the provider folder
        current_path = os.path.abspath(__file__)
        entities_path = os.path.dirname(current_path)
        provider_path = os.path.join(os.path.dirname(entities_path), "providers", provider_entity.name)

        # 5. Load positions.yaml (model ordering)
        positions_yaml_path = os.path.join(provider_path, "positions.yaml")
        with open(positions_yaml_path, encoding="utf-8") as f:
            positions_yaml_data = yaml.safe_load(f) or []
        if not isinstance(positions_yaml_data, list):
            raise FailException("positions.yaml format error")

        # 6. Iterate through model names found in positions.yaml
        for model_name in positions_yaml_data:
            # 7. Build path to the model YAML file
            model_yaml_path = os.path.join(provider_path, f"{model_name}.yaml")
            with open(model_yaml_path, encoding="utf-8") as f:
                model_yaml_data = yaml.safe_load(f)

            # 8. Parse parameters from the YAML file
            yaml_parameters = model_yaml_data.get("parameters")
            parameters = []
            for parameter in yaml_parameters:
                # 9. Check whether the parameter uses a template
                use_template = parameter.get("use_template")
                if use_template:
                    # 10. Apply template defaults, remove use_template
                    default_parameter = DEFAULT_MODEL_PARAMETER_TEMPLATE.get(use_template)
                    del parameter["use_template"]
                    parameters.append({**default_parameter, **parameter})
                else:
                    # 11. Use raw configuration as-is
                    parameters.append(parameter)

            # 12. Replace parameters in YAML with resolved data, create ModelEntity
            model_yaml_data["parameters"] = parameters
            provider["model_entity_map"][model_name] = ModelEntity(**model_yaml_data)

        return provider

    def get_model_class(self, model_type: ModelType) -> Optional[Type[BaseLanguageModel]]:
        """Retrieve a model class based on model type"""
        model_class = self.model_class_map.get(model_type, None)
        if model_class is None:
            raise NotFoundException("The model class does not exist. Please verify and try again.")
        return model_class

    def get_model_entity(self, model_name: str) -> Optional[ModelEntity]:
        """Retrieve model entity metadata based on model name"""
        model_entity = self.model_entity_map.get(model_name, None)
        if model_entity is None:
            raise NotFoundException("The model entity does not exist. Please verify and try again.")
        return model_entity

    def get_model_entities(self) -> list[ModelEntity]:
        """Retrieve all model entities under this provider"""
        return list(self.model_entity_map.values())
