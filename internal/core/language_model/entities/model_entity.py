#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : model_entity.py
"""
from abc import ABC
from enum import Enum
from typing import Any, Optional

from langchain_core.language_models import BaseLanguageModel as LCBaseLanguageModel
from langchain_core.pydantic_v1 import BaseModel, Field


class DefaultModelParameterName(str, Enum):
    """Default parameter names — parameters commonly shared across LLMs"""
    TEMPERATURE = "temperature"  # Temperature
    TOP_P = "top_p"  # Nucleus sampling rate
    PRESENCE_PENALTY = "presence_penalty"  # Presence penalty
    FREQUENCY_PENALTY = "frequency_penalty"  # Frequency penalty
    MAX_TOKENS = "max_tokens"  # Max number of tokens to generate


class ModelType(str, Enum):
    """Model type enum"""
    CHAT = "chat"  # Chat model
    COMPLETION = "completion"  # Text generation model


class ModelParameterType(str, Enum):
    """Model parameter data type"""
    FLOAT = "float"
    INT = "int"
    STRING = "string"
    BOOLEAN = "boolean"


class ModelParameterOption(BaseModel):
    """Model parameter option configuration"""
    label: str  # Option label
    value: Any  # Value corresponding to the option


class ModelParameter(BaseModel):
    """Model parameter entity"""
    name: str = ""  # Parameter name
    label: str = ""  # Display label
    type: ModelParameterType = ModelParameterType.STRING  # Parameter type
    help: str = ""  # Help text
    required: bool = False  # Whether parameter is required
    default: Optional[Any] = None  # Default value
    min: Optional[float] = None  # Minimum allowed value
    max: Optional[float] = None  # Maximum allowed value
    precision: int = 2  # Decimal precision
    options: list[ModelParameterOption] = Field(default_factory=list)  # Optional configuration options


class ModelFeature(str, Enum):
    """
    Model features used to mark capabilities such as:
    - Tool calling
    - Agent reasoning
    - Image input (multimodal)
    """
    TOOL_CALL = "tool_call"  # Supports tool calling
    AGENT_THOUGHT = "agent_thought"  # Supports agent-style reasoning; typically requires larger models capable of multi-step reasoning. Smaller models may produce direct answers without intermediate reasoning steps.
    IMAGE_INPUT = "image_input"  # Supports image input (multimodal LLMs)


class ModelEntity(BaseModel):
    """Language model entity storing model-related information"""
    model_name: str = Field(default="", alias="model")  # Model name (alias: model)
    label: str = ""  # Display label
    model_type: ModelType = ModelType.CHAT  # Model type
    features: list[ModelFeature] = Field(default_factory=list)  # Supported model features
    context_window: int = 0  # Context window size (input + output)
    max_output_tokens: int = 0  # Maximum output length (tokens)
    attributes: dict[str, Any] = Field(default_factory=dict)  # Fixed attributes specific to the model
    parameters: list[ModelParameter] = Field(default_factory=list)  # Parameter configuration rules
    metadata: dict[str, Any] = Field(default_factory=dict)  # Extra model metadata such as pricing, vocab size, etc.


class BaseLanguageModel(LCBaseLanguageModel, ABC):
    """Base language model"""
    features: list[ModelFeature] = Field(default_factory=list)  # Supported features
    metadata: dict[str, Any] = Field(default_factory=dict)  # Model metadata
