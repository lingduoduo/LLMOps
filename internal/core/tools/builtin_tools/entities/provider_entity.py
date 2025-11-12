#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : provider_entity.py
"""
import os.path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from internal.lib.helper import dynamic_import
from .tool_entity import ToolEntity


class ProviderEntity(BaseModel):
    """Service provider entity, mapping each record in providers.yaml"""
    name: str  # Name
    label: str  # Label displayed to the front end
    description: str  # Description
    icon: str  # Icon URL
    background: str  # Icon background color
    category: str  # Category information
    created_at: int = 0  # Timestamp when the provider/tool was created


class Provider(BaseModel):
    """Service provider class, contains all tools, descriptions, icons, and related information"""
    name: str  # Name of the service provider
    position: int  # Order/position of the service provider
    provider_entity: ProviderEntity  # Service provider entity
    tool_entity_map: dict[str, ToolEntity] = Field(default_factory=dict)  # Mapping of tool entities
    tool_func_map: dict[str, Any] = Field(default_factory=dict)  # Mapping of tool functions

    def __init__(self, **kwargs):
        """Constructor, initializes the service provider"""
        super().__init__(**kwargs)
        self._provider_init()

    def get_tool(self, tool_name: str) -> Any:
        """Get a specific tool of the service provider by name"""
        return self.tool_func_map.get(tool_name)

    def get_tool_entity(self, tool_name: str) -> ToolEntity:
        """Get the entity/information of a specific tool by name"""
        return self.tool_entity_map.get(tool_name)

    def get_tool_entities(self) -> list[ToolEntity]:
        """Get a list of all tool entities under the service provider"""
        return list(self.tool_entity_map.values())

    def _provider_init(self):
        """Service provider initialization function"""
        # 1. Get the current file path to compute the service provider directory
        current_path = os.path.abspath(__file__)
        entities_path = os.path.dirname(current_path)
        provider_path = os.path.join(os.path.dirname(entities_path), "providers", self.name)

        # 2. Construct the path to positions.yaml and load the data
        positions_yaml_path = os.path.join(provider_path, "positions.yaml")
        with open(positions_yaml_path, encoding="utf-8") as f:
            positions_yaml_data = yaml.safe_load(f)

        # 3. Iterate through the position information to get tool names
        for tool_name in positions_yaml_data:
            # 4. Load the tool's YAML data
            tool_yaml_path = os.path.join(provider_path, f"{tool_name}.yaml")
            with open(tool_yaml_path, encoding="utf-8") as f:
                tool_yaml_data = yaml.safe_load(f)

            # 5. Populate the tool_entity_map with tool entity data
            self.tool_entity_map[tool_name] = ToolEntity(**tool_yaml_data)

            # 6. Dynamically import the tool and populate tool_func_map
            self.tool_func_map[tool_name] = dynamic_import(
                f"internal.core.tools.builtin_tools.providers.{self.name}",
                tool_name,
            )
