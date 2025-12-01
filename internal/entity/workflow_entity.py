#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : workflow_entity.py
"""
from enum import Enum


class WorkflowStatus(str, Enum):
    """Workflow status enumeration"""
    DRAFT = "draft"
    PUBLISHED = "published"


class WorkflowResultStatus(str, Enum):
    """Workflow execution result status"""
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# Default workflow configuration — creates an empty workflow by default
DEFAULT_WORKFLOW_CONFIG = {
    "graph": {},
    "draft_graph": {
        "nodes": [],
        "edges": []
    },
}
