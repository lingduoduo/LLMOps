#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : dataset_retrieval_entity.py
"""
from uuid import UUID

from langchain_core.pydantic_v1 import BaseModel, Field, validator

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import (
    VariableEntity,
    VariableType,
    VariableValueType,
)
from internal.entity.dataset_entity import RetrievalStrategy
from internal.exception import FailException


class RetrievalConfig(BaseModel):
    """Retrieval configuration."""
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.SEMANTIC  # Retrieval strategy
    k: int = 4  # Max number of results to return
    score: float = 0  # Score threshold


class DatasetRetrievalNodeData(BaseNodeData):
    """Dataset / knowledge-base retrieval node data."""
    dataset_ids: list[UUID]  # List of associated dataset IDs
    retrieval_config: RetrievalConfig = RetrievalConfig()  # Retrieval configuration
    inputs: list[VariableEntity] = Field(default_factory=list)  # Input variable list
    outputs: list[VariableEntity] = Field(
        exclude=True,
        default_factory=lambda: [
            VariableEntity(
                name="combine_documents",
                value={"type": VariableValueType.GENERATED},
            )
        ],
    )

    @validator("inputs")
    def validate_inputs(cls, value: list[VariableEntity]):
        """
        Validate the input variable configuration for the retrieval node.

        Requirements:
        - Exactly one input variable.
        - Variable must be named "query".
        - Type must be STRING.
        - It must be required.
        """
        # 1. Must have exactly one input variable
        if len(value) != 1:
            raise FailException("Dataset retrieval node must have exactly one input variable.")

        # 2. Validate the variable's name, type, and required flag
        query_input = value[0]
        if (
                query_input.name != "query"
                or query_input.type != VariableType.STRING
                or query_input.required is False
        ):
            raise FailException("Invalid input variable: expected a required STRING variable named 'query'.")

        return value
