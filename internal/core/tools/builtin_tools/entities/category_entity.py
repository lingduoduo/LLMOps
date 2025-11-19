#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : category_entity.py
"""
from pydantic import BaseModel, field_validator

from internal.exception import FailException


class CategoryEntity(BaseModel):
    """Category entity"""
    category: str  # Unique category identifier
    name: str  # Category display name
    icon: str  # Icon filename for the category

    @field_validator("icon")
    def check_icon_extension(cls, value: str):
        """Validate that the icon file has a .svg extension; raise an error if not."""
        if not value.endswith(".svg"):
            raise FailException("Icon for this category must have a .svg extension")
        return value
