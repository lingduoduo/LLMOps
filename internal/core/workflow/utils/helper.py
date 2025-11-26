#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : helper.py
"""
from typing import Any

from internal.core.workflow.entities.variable_entity import (
    VariableEntity,
    VariableValueType,
    VARIABLE_TYPE_MAP,
    VARIABLE_TYPE_DEFAULT_VALUE_MAP,
)
from internal.core.workflow.entities.workflow_entity import WorkflowState


def extract_variables_from_state(variables: list[VariableEntity], state: WorkflowState) -> dict[str, Any]:
    """Extract variable-value mappings from workflow state"""
    # 1. Build the variable dictionary
    variables_dict = {}

    # 2. Iterate through all input variable entities
    for variable in variables:
        # 3. Get the Python type class for this variable type
        variable_type_cls = VARIABLE_TYPE_MAP.get(variable.type)

        # 4. Determine whether the value is a literal or a reference
        if variable.value.type == VariableValueType.LITERAL:
            variables_dict[variable.name] = variable_type_cls(variable.value.content)
        else:
            # 5. For referenced/generated values, iterate through node results to locate data
            for node_result in state["node_results"]:
                if node_result.node_data.id == variable.value.content.ref_node_id:
                    # 6. Extract the value and cast to the proper type
                    variables_dict[variable.name] = variable_type_cls(
                        node_result.outputs.get(
                            variable.value.content.ref_var_name,
                            VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(variable.type)
                        )
                    )
    return variables_dict
