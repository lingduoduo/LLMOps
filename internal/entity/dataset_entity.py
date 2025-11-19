#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : dataset_entity.py
"""
from enum import Enum

# Default dataset description template
DEFAULT_DATASET_DESCRIPTION_FORMATTER = "When you need to answer questions about \"{name}\", you can refer to this knowledge base."


class ProcessType(str, Enum):
    """Document processing rule type enum"""
    AUTOMATIC = "automatic"
    CUSTOM = "custom"


# Default processing rule
DEFAULT_PROCESS_RULE = {
    "mode": "custom",
    "rule": {
        "pre_process_rules": [
            {"id": "remove_extra_space", "enabled": True},
            {"id": "remove_url_and_email", "enabled": True},
        ],
        "segment": {
            "separators": [
                "\n\n",
                "\n",
                "。|！|？",
                "\.\s|\!\s|\?\s",  # A space is typically required after English punctuation
                "；|;\s",
                "，|,\s",
                " ",
                ""
            ],
            "chunk_size": 500,
            "chunk_overlap": 50,
        }
    }
}


class DocumentStatus(str, Enum):
    """Document status type enum"""
    WAITING = "waiting"
    PARSING = "parsing"
    SPLITTING = "splitting"
    INDEXING = "indexing"
    COMPLETED = "completed"
    ERROR = "error"


class SegmentStatus(str, Enum):
    """Segment status type enum"""
    WAITING = "waiting"
    INDEXING = "indexing"
    COMPLETED = "completed"
    ERROR = "error"


class RetrievalStrategy(str, Enum):
    """Retrieval strategy type enum"""
    FULL_TEXT = "full_text"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class RetrievalSource(str, Enum):
    """Retrieval source"""
    HIT_TESTING = "hit_testing"
    APP = "app"
    DEBUGGER = "debugger"
