#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : default_model_parameter_template.py
"""
from .model_entity import DefaultModelParameterName, ModelParameterType

# Default model parameter template to reduce YAML configuration.
# Parameters follow the OpenAI model API conventions.
DEFAULT_MODEL_PARAMETER_TEMPLATE = {
    # Temperature default parameter
    DefaultModelParameterName.TEMPERATURE: {
        "label": "Temperature",
        "type": ModelParameterType.FLOAT,
        "help": "Controls randomness. Lower temperature results in less random output. "
                "As the temperature approaches zero, the model becomes deterministic; "
                "higher temperature produces more diverse outputs.",
        "required": False,
        "default": 1,
        "min": 0,
        "max": 2,
        "precision": 2,
        "options": [],
    },
    # Top-P nucleus sampling
    DefaultModelParameterName.TOP_P: {
        "label": "Top P",
        "type": ModelParameterType.FLOAT,
        "help": "Controls diversity via nucleus sampling. For example, 0.5 means considering "
                "only the top 50% probability mass.",
        "required": False,
        "default": 0,
        "min": 0,
        "max": 1,
        "precision": 2,
        "options": [],
    },
    # Presence penalty
    DefaultModelParameterName.PRESENCE_PENALTY: {
        "label": "Presence Penalty",
        "type": ModelParameterType.FLOAT,
        "help": "Applies a penalty to the log probability of tokens already appearing in the text.",
        "required": False,
        "default": 0,
        "min": -2.0,
        "max": 2.0,
        "precision": 2,
        "options": [],
    },
    # Frequency penalty
    DefaultModelParameterName.FREQUENCY_PENALTY: {
        "label": "Frequency Penalty",
        "type": ModelParameterType.FLOAT,
        "help": "Applies a penalty to the log probability proportional to how frequently a token "
                "appears in the text.",
        "required": False,
        "default": 0,
        "min": -2.0,
        "max": 2.0,
        "precision": 2,
        "options": [],
    },
    # Maximum number of tokens to generate
    DefaultModelParameterName.MAX_COMPLETION_TOKENS: {
        "label": "Max Tokens",
        "type": ModelParameterType.INT,
        "help": "The maximum number of tokens to generate (integer).",
        "required": False,
        "default": None,
        "min": 1,
        "max": 16384,
        "precision": 0,
        "options": [],
    },
}
