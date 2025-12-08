#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : app_entity.py
"""
from enum import Enum

# Icon description prompt template
GENERATE_ICON_PROMPT_TEMPLATE = """You are an AI image-generation engineer with 10 years of experience. 
Your task is to convert the user's `application name` and `application description` into an English icon description.
This description will be used for DALL·E image generation.

The user-provided data is as follows:

Application Name: {name}
Application Description: {description}

Generate only the icon description prompt—do not output anything else."""


class AppStatus(str, Enum):
    """Application status enum"""
    DRAFT = "draft"
    PUBLISHED = "published"


class AppConfigType(str, Enum):
    """Application configuration type enum"""
    DRAFT = "draft"
    PUBLISHED = "published"


# Default application configuration
DEFAULT_APP_CONFIG = {
    "model_config": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "parameters": {
            "temperature": 0.5,
            "top_p": 0.85,
            "frequency_penalty": 0.2,
            "presence_penalty": 0.2,
            "max_tokens": 8192,
        },
    },
    "dialog_round": 3,
    "preset_prompt": "",
    "tools": [],
    "workflows": [],
    "datasets": [],
    "retrieval_config": {
        "retrieval_strategy": "semantic",
        "k": 10,
        "score": 0.5,
    },
    "long_term_memory": {
        "enable": False,
    },
    "opening_statement": "",
    "opening_questions": [],
    "speech_to_text": {
        "enable": False,
    },
    "text_to_speech": {
        "enable": False,
        "voice": "echo",
        "auto_play": False,
    },
    "suggested_after_answer": {
        "enable": True,
    },
    "review_config": {
        "enable": False,
        "keywords": [],
        "inputs_config": {
            "enable": False,
            "preset_response": "",
        },
        "outputs_config": {
            "enable": False,
        },
    },
}
