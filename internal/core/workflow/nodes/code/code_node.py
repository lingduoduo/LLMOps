#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : code_node.py
"""

import ast
import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.variable_entity import VARIABLE_TYPE_DEFAULT_VALUE_MAP
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from internal.exception import FailException
from .code_entity import CodeNodeData


class CodeNode(BaseNode):
    """Node that executes restricted Python code."""
    node_data: CodeNodeData

    def invoke(
            self,
            state: WorkflowState,
            config: Optional[RunnableConfig] = None
    ) -> WorkflowState:
        """
        Execute the Python code contained in this node.

        Requirements / Constraints:
        - Code must define exactly one function named `main`.
        - The `main` function must take exactly one argument named `params`.
        - No other statements or functions are allowed.
        - The return value of `main` must be a dictionary.
        """
        # 1. Extract input variables
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 2. Execute Python code (currently unsafe — should be sandboxed in future)
        result = self._execute_function(self.node_data.code, params=inputs_dict)

        # 3. Validate return type
        if not isinstance(result, dict):
            raise FailException("The return value of main() must be a dictionary.")

        # 4. Extract output values
        outputs_dict = {}
        outputs = self.node_data.outputs
        for output in outputs:
            outputs_dict[output.name] = result.get(
                output.name,
                VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(output.type),
            )

        # 5. Build and return workflow node result
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs_dict,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }

    @classmethod
    def _execute_function(cls, code: str, *args, **kwargs):
        """Parse, validate, and execute the provided Python code."""
        try:
            # 1. Parse into AST
            tree = ast.parse(code)

            main_func = None

            # 2. Validate AST: must contain ONE function named main(params)
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    # main function
                    if node.name == "main":
                        if main_func:
                            raise FailException("Only one main function is allowed.")

                        # Validate function signature
                        if len(node.args.args) != 1 or node.args.args[0].arg != "params":
                            raise FailException("main() must accept exactly one argument named 'params'.")

                        main_func = node
                    else:
                        raise FailException("Only the main function is allowed; no other functions permitted.")
                else:
                    raise FailException("Only function definitions are allowed; no additional statements permitted.")

            if not main_func:
                raise FailException("A function named main() is required.")

            # 3. Execute the code
            local_vars = {}
            exec(code, {}, local_vars)

            # 4. Execute main(params)
            if "main" in local_vars and callable(local_vars["main"]):
                return local_vars["main"](*args, **kwargs)
            else:
                raise FailException("main() must be a callable function.")
        except Exception:
            raise FailException("Python code execution failed.")
