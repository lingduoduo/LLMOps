#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : language_model_manager.py
"""
import os.path
from typing import Any, Optional, Type

import yaml
from injector import inject, singleton
from langchain_core.pydantic_v1 import BaseModel, Field, root_validator

from internal.exception import NotFoundException
from .entities.model_entity import ModelType, BaseLanguageModel
from .entities.provider_entity import Provider, ProviderEntity


@inject
@singleton
class LanguageModelManager(BaseModel):
    """Language Model Manager"""
    provider_map: dict[str, Provider] = Field(default_factory=dict)  # Mapping of service providers

    @root_validator(pre=False)
    def validate_language_model_manager(cls, values: dict[str, Any]) -> dict[str, Any]:
        """
        Use preset validation rules provided by Pydantic to validate
        the provider mapping and complete the initialization of the
        language model manager.
        """
        # 1. Get the current class file path
        current_path = os.path.abspath(__file__)
        providers_path = os.path.join(os.path.dirname(current_path), "providers")
        providers_yaml_path = os.path.join(providers_path, "providers.yaml")

        # 2. Read providers.yaml to load the provider configuration list
        with open(providers_yaml_path, encoding="utf-8") as f:
            providers_yaml_data = yaml.safe_load(f)

        # 3. Loop through provider data and configure model information
        values["provider_map"] = {}
        for index, provider_yaml_data in enumerate(providers_yaml_data):
            # 4. Parse provider entity data structure and build provider entity
            provider_entity = ProviderEntity(**provider_yaml_data)
            values["provider_map"][provider_entity.name] = Provider(
                name=provider_entity.name,
                position=index + 1,
                provider_entity=provider_entity,
            )
        return values

    def get_provider(self, provider_name: str) -> Optional[Provider]:
        """Retrieve a provider by its name"""
        provider = self.provider_map.get(provider_name, None)
        if provider is None:
            raise NotFoundException("The model service provider does not exist. Please verify and try again.")
        return provider

    def get_providers(self) -> list[Provider]:
        """Retrieve all provider information"""
        return list(self.provider_map.values())

    def get_model_class_by_provider_and_type(
            self,
            provider_name: str,
            model_type: ModelType,
    ) -> Optional[Type[BaseLanguageModel]]:
        """Retrieve a model class based on provider name + model type"""
        provider = self.get_provider(provider_name)

        return provider.get_model_class(model_type)

    def get_model_class_by_provider_and_model(
            self,
            provider_name: str,
            model_name: str,
    ) -> Optional[Type[BaseLanguageModel]]:
        """Retrieve a model class based on provider name + model name"""
        # 1. Retrieve provider information by name
        provider = self.get_provider(provider_name)

        # 2. Retrieve the model entity under the provider
        model_entity = provider.get_model_entity(model_name)

        return provider.get_model_class(model_entity.model_type)
