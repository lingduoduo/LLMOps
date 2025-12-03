#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : category_entity.py
"""
from pydantic import BaseModel, Field


class CategoryEntity(BaseModel):
    """Builtin application category entity"""
    category: str = Field(default="")  # Unique category identifier
    name: str = Field(default="")  # Display name for this category
