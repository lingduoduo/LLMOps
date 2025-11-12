#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : builtin_provider_manager.py
"""
import os.path
from typing import Any

import yaml
from injector import inject, singleton
from pydantic import BaseModel, Field

from internal.core.tools.builtin_tools.entities import ProviderEntity, Provider


@inject
@singleton
class BuiltinProviderManager(BaseModel):
    """Factory class for service providers"""
    provider_map: dict[str, Provider] = Field(default_factory=dict)

    def __init__(self, **kwargs):
        """Constructor: initializes the provider-to-tool mapping"""
        super().__init__(**kwargs)
        self._get_provider_tool_map()

    def get_provider(self, provider_name: str) -> Provider:
        """Retrieve a provider by its name."""
        return self.provider_map.get(provider_name)

    def get_providers(self) -> list[Provider]:
        """Get a list of all providers."""
        return list(self.provider_map.values())

    def get_provider_entities(self) -> list[ProviderEntity]:
        """Get a list of all provider entity details."""
        return [provider.provider_entity for provider in self.provider_map.values()]

    def get_tool(self, provider_name: str, tool_name: str) -> Any:
        """Retrieve a specific tool from a given provider."""
        provider = self.get_provider(provider_name)
        if provider is None:
            return None
        return provider.get_tool(tool_name)

    def _get_provider_tool_map(self):
        """
        On initialization, load the mapping between providers and their tools
        from the providers.yaml configuration file.
        """
        # 1. If the map is already populated, do nothing
        if self.provider_map:
            return

        # 2. Determine the directory of this file
        current_path = os.path.abspath(__file__)
        providers_path = os.path.dirname(current_path)
        providers_yaml_path = os.path.join(providers_path, "providers.yaml")

        # 3. Read the providers.yaml file
        with open(providers_yaml_path, encoding="utf-8") as f:
            providers_yaml_data = yaml.safe_load(f)

        # 4. Populate the provider_map from the YAML data
        for idx, provider_data in enumerate(providers_yaml_data):
            provider_entity = ProviderEntity(**provider_data)
            self.provider_map[provider_entity.name] = Provider(
                name=provider_entity.name,
                position=idx + 1,
                provider_entity=provider_entity
            )
