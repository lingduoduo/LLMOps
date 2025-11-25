#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : http_request_node.py
"""
import time
from typing import Optional

import requests
from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from .http_request_entity import (
    HttpRequestInputType,
    HttpRequestMethod,
    HttpRequestNodeData,
)


class HttpRequestNode(BaseNode):
    """HTTP request node."""
    node_data: HttpRequestNodeData

    def invoke(
            self,
            state: WorkflowState,
            config: Optional[RunnableConfig] = None
    ) -> WorkflowState:
        """
        Execute the HTTP request node.

        Steps:
        1. Extract input variables from workflow state.
        2. Categorize them into params / headers / body.
        3. Dispatch an HTTP request using the configured method and URL.
        4. Return the response text and HTTP status code.
        """
        # 1. Extract variable values for this node
        start_at = time.perf_counter()
        _inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 2. Split variables into params, headers, and body
        inputs_dict = {
            HttpRequestInputType.PARAMS: {},
            HttpRequestInputType.HEADERS: {},
            HttpRequestInputType.BODY: {},
        }
        for input in self.node_data.inputs:
            # Determine which type this variable belongs to (params, headers, body)
            inputs_dict[input.meta.get("type")][input.name] = _inputs_dict.get(input.name)

        # 3. Map HTTP methods to requests functions
        request_methods = {
            HttpRequestMethod.GET: requests.get,
            HttpRequestMethod.POST: requests.post,
            HttpRequestMethod.PUT: requests.put,
            HttpRequestMethod.PATCH: requests.patch,
            HttpRequestMethod.DELETE: requests.delete,
            HttpRequestMethod.HEAD: requests.head,
            HttpRequestMethod.OPTIONS: requests.options,
        }

        # 4. Dispatch the HTTP request
        request_method = request_methods[self.node_data.method]
        if self.node_data.method == HttpRequestMethod.GET:
            response = request_method(
                self.node_data.url,
                headers=inputs_dict[HttpRequestInputType.HEADERS],
                params=inputs_dict[HttpRequestInputType.PARAMS],
            )
        else:
            # 5. Non-GET methods send body as well
            response = request_method(
                self.node_data.url,
                headers=inputs_dict[HttpRequestInputType.HEADERS],
                params=inputs_dict[HttpRequestInputType.PARAMS],
                data=inputs_dict[HttpRequestInputType.BODY],
            )

        # 6. Extract response text and status code
        text = response.text
        status_code = response.status_code

        # 7. Build output payload
        outputs = {
            "text": text,
            "status_code": status_code,
        }

        # 8. Build workflow node result
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }
