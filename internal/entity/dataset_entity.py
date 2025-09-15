#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/8/25 14:34
@Author  : thezehui@gmail.com
@File    : dataset_entity.py
"""
from enum import Enum

# Default knowledge base description template
DEFAULT_DATASET_DESCRIPTION_FORMATTER = (
    'When answering questions about managing "{name}", you may reference this knowledge base.'
)


class ProcessType(str, Enum):
    """Document processing rule type enum"""
    AUTOMATIC = "automatic"
    CUSTOM = "custom"


# Default processing rules
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
                r"\.\s|\!\s|\?\s",  # English punctuation is typically followed by a space
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
    """Document status enum"""
    WAITING = "waiting"
    PARSING = "parsing"
    SPLITTING = "splitting"
    INDEXING = "indexing"
    COMPLETED = "completed"
    ERROR = "error"


class SegmentStatus(str, Enum):
    """Segment status enum"""
    WAITING = "waiting"
    INDEXING = "indexing"
    COMPLETED = "completed"
    ERROR = "error"


class RetrievalStrategy(str, Enum):
    """Retrieval strategy enum"""
    FULL_TEXT = "full_text"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class RetrievalSource(str, Enum):
    """Retrieval source"""
    HIT_TESTING = "hit_testing"
    APP = "app"
