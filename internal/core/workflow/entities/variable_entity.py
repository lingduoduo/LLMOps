#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : variable_entity.py
"""
import re
from enum import Enum
from typing import Union, Any
from uuid import UUID

from langchain_core.pydantic_v1 import BaseModel, Field, validator

from internal.exception import ValidateErrorException


class VariableType(str, Enum):
    """Enum for variable value types."""
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOLEAN = "boolean"


# Mapping from variable type enum to Python types
VARIABLE_TYPE_MAP = {
    VariableType.STRING: str,
    VariableType.INT: int,
    VariableType.FLOAT: float,
    VariableType.BOOLEAN: bool,
}

# Default values for each variable type
VARIABLE_TYPE_DEFAULT_VALUE_MAP = {
    VariableType.STRING: "",
    VariableType.INT: 0,
    VariableType.FLOAT: 0,
    VariableType.BOOLEAN: False,
}

# Variable name regex (letters, digits, underscore; must start with letter or underscore)
VARIABLE_NAME_PATTERN = r'^[A-Za-z_][A-Za-z0-9_]*$'

# Max description length
VARIABLE_DESCRIPTION_MAX_LENGTH = 1024


class VariableValueType(str, Enum):
    """Enum for the kind of stored value."""
    REF = "ref"  # Reference to another node's variable
    LITERAL = "literal"  # Literal / direct value
    GENERATED = "generated"  # Generated value, often used at start nodes or outputs


class VariableEntity(BaseModel):
    """Variable definition and value metadata."""

    class Value(BaseModel):
        """Container for a variable's value and its representation type."""

        class Content(BaseModel):
            """
            Referenced value metadata.

            When `type` is REF, this stores:
            - ref_node_id: ID of the node being referenced
            - ref_var_name: variable name on the referenced node
            """
            ref_node_id: UUID
            ref_var_name: str

        type: VariableValueType = VariableValueType.LITERAL
        content: Union[Content, str, int, float, bool] = ""

    # Variable name
    name: str = ""

    # Description of the variable
    description: str = ""

    # Whether this variable is required
    required: bool = True

    # Variable type
    type: VariableType = VariableType.STRING

    # Variable value
    value: Value = Field(
        default_factory=lambda: {"type": VariableValueType.LITERAL, "content": ""}
    )

    # Extra metadata (e.g., HTTP param type, UI hints, etc.)
    meta: dict[str, Any] = Field(default_factory=dict)

    @validator("name")
    def validate_name(cls, value: str) -> str:
        """Validate variable name using the allowed pattern."""
        if not re.match(VARIABLE_NAME_PATTERN, value):
            raise ValidateErrorException(
                "Variable name may only contain letters, digits, and underscores, "
                "and must start with a letter or underscore."
            )
        return value

    @validator("description")
    def validate_description(cls, value: str) -> str:
        """Validate and truncate description to the maximum allowed length."""
        return value[:VARIABLE_DESCRIPTION_MAX_LENGTH]
