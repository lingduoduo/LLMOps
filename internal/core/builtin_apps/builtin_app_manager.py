#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : builtin_app_manager.py
"""
import os

import yaml
from injector import inject, singleton
from pydantic import BaseModel, Field

from internal.core.builtin_apps.entities.builtin_app_entity import BuiltinAppEntity
from internal.core.builtin_apps.entities.category_entity import CategoryEntity


@inject
@singleton
class BuiltinAppManager(BaseModel):
    """Builtin app manager"""
    builtin_app_map: dict[str, BuiltinAppEntity] = Field(default_factory=dict)
    categories: list[CategoryEntity] = Field(default_factory=list)

    def __init__(self, **kwargs):
        """Constructor, initializes builtin_app_map and categories"""
        super().__init__(**kwargs)
        self._init_categories()
        self._init_builtin_app_map()

    def get_builtin_app(self, builtin_app_id: str) -> BuiltinAppEntity | None:
        """Get a builtin app by its ID"""
        return self.builtin_app_map.get(builtin_app_id, None)

    def get_builtin_apps(self) -> list[BuiltinAppEntity]:
        """Get the list of all builtin apps"""
        return [builtin_app_entity for builtin_app_entity in self.builtin_app_map.values()]

    def get_categories(self) -> list[CategoryEntity]:
        """Get the list of builtin app categories"""
        return self.categories

    def _init_builtin_app_map(self):
        """Initialize all builtin apps when the manager is created"""
        # 1. If builtin_app_map is already initialized, do nothing
        if self.builtin_app_map:
            return

        # 2. Get the directory path where this file/class is located
        current_path = os.path.abspath(__file__)
        parent_path = os.path.dirname(current_path)
        builtin_apps_yaml_path = os.path.join(parent_path, "builtin_apps")

        # 3. Iterate through all YAML files under builtin_apps_yaml_path
        for filename in os.listdir(builtin_apps_yaml_path):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                file_path = os.path.join(builtin_apps_yaml_path, filename)

                # 4. Load YAML data
                with open(file_path, encoding="utf-8") as f:
                    builtin_app = yaml.safe_load(f)

                # 5. Initialize builtin app data and add to the map
                builtin_app["language_model_config"] = builtin_app.pop("model_config")
                self.builtin_app_map[builtin_app.get("id")] = BuiltinAppEntity(**builtin_app)

    def _init_categories(self):
        """Initialize the builtin app category list"""
        # 1. If categories are already initialized, do nothing
        if self.categories:
            return

        # 2. Get the directory path where this file/class is located
        current_path = os.path.abspath(__file__)
        parent_path = os.path.dirname(current_path)
        categories_yaml_path = os.path.join(parent_path, "categories", "categories.yaml")

        # 3. Load YAML data
        with open(categories_yaml_path, encoding="utf-8") as f:
            categories = yaml.safe_load(f)

        # 4. Iterate through all category records and initialize them
        for category in categories:
            self.categories.append(CategoryEntity(**category))
