#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : builtin_category_manager.py
"""
import os.path
from typing import Any

import yaml
from injector import inject, singleton
from pydantic import BaseModel, Field

from internal.core.tools.builtin_tools.entities import CategoryEntity
from internal.exception import NotFoundException


@inject
@singleton
class BuiltinCategoryManager(BaseModel):
    """Built-in tool category manager."""
    category_map: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **kwargs):
        """Initialize the category manager."""
        super().__init__(**kwargs)
        self._init_categories()

    def get_category_map(self) -> dict[str, Any]:
        """Return the mapping of categories."""
        return self.category_map

    def _init_categories(self):
        """Load and initialize category data."""
        # 1. Check if categories have already been initialized
        if self.category_map:
            return

        # 2. Build the path to the YAML file and load its content
        current_path = os.path.abspath(__file__)
        category_path = os.path.dirname(current_path)
        category_yaml_path = os.path.join(category_path, "categories.yaml")
        with open(category_yaml_path, encoding="utf-8") as f:
            categories = yaml.safe_load(f)

        # 3. Iterate over all categories and convert each into an entity
        for category in categories:
            # 4. Instantiate a CategoryEntity from the YAML data
            category_entity = CategoryEntity(**category)

            # 5. Verify that the icon file exists
            icon_path = os.path.join(category_path, "icons", category_entity.icon)
            if not os.path.exists(icon_path):
                raise NotFoundException(
                    f"Icon for category '{category_entity.category}' was not provided"
                )

            # 6. Read the icon file contents
            with open(icon_path, encoding="utf-8") as f:
                icon = f.read()

            # 7. Map the category key to its entity and icon data
            self.category_map[category_entity.category] = {
                "entity": category_entity,
                "icon": icon,
            }
