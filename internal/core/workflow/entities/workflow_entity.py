#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    : workflow_entity.py
"""
import re
from collections import defaultdict, deque
from typing import Any, TypedDict, Annotated
from uuid import UUID

from langchain_core.pydantic_v1 import BaseModel, Field, root_validator

from internal.exception import ValidateErrorException
from .edge_entity import BaseEdgeData
from .node_entity import BaseNodeData, NodeResult, NodeType
from .variable_entity import VariableEntity, VariableValueType

# Workflow configuration validation rules
WORKFLOW_CONFIG_NAME_PATTERN = r'^[A-Za-z_][A-Za-z0-9_]*$'
WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH = 1024


def _process_dict(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Reducer for workflow state dict fields (inputs / outputs)."""
    # 1. Handle None cases
    left = left or {}
    right = right or {}

    # 2. Merge dictionaries (right overwrites left on conflicts)
    return {**left, **right}


def _process_node_results(left: list[NodeResult], right: list[NodeResult]) -> list[NodeResult]:
    """Reducer for workflow node_results lists."""
    # 1. Handle None cases
    left = left or []
    right = right or []

    # 2. Concatenate node result lists
    return left + right


class WorkflowConfig(BaseModel):
    """
    Workflow configuration.

    Includes:
    - account_id: owner / tenant identifier
    - name: workflow identifier (for tools / code)
    - description: description for LLMs on when to call this workflow
    - nodes: list of node definitions
    - edges: list of edge definitions
    """
    account_id: UUID  # Account / user identifier
    name: str = ""  # Workflow name; must be English-like identifier
    description: str = ""  # Workflow description, used to tell LLM when to call it
    nodes: list[BaseNodeData] = Field(default_factory=list)  # Node list
    edges: list[BaseEdgeData] = Field(default_factory=list)  # Edge list

    @root_validator(pre=True)
    def validate_workflow_config(cls, values: dict[str, Any]):
        """Validate the entire workflow configuration."""
        # 1. Validate workflow name
        name = values.get("name", None)
        if not name or not re.match(WORKFLOW_CONFIG_NAME_PATTERN, name):
            raise ValidateErrorException(
                "Workflow name must contain only letters, digits, and underscores, "
                "and must start with a letter or underscore."
            )

        # 2. Validate workflow description length (used by LLM, <= 1024 chars)
        description = values.get("description", None)
        if not description or len(description) > WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH:
            raise ValidateErrorException(
                "Workflow description must not be empty and cannot exceed 1024 characters."
            )

        # 3. Get node and edge lists
        nodes = values.get("nodes", [])
        edges = values.get("edges", [])

        # 4. Basic checks for nodes / edges
        if not isinstance(nodes, list) or len(nodes) <= 0:
            raise ValidateErrorException("Invalid workflow node list. Please verify and try again.")
        if not isinstance(edges, list) or len(edges) <= 0:
            raise ValidateErrorException("Invalid workflow edge list. Please verify and try again.")

        # 5. Node data class mapping
        from internal.core.workflow.nodes import (
            CodeNodeData,
            DatasetRetrievalNodeData,
            EndNodeData,
            HttpRequestNodeData,
            LLMNodeData,
            StartNodeData,
            TemplateTransformNodeData,
            ToolNodeData,
        )
        node_data_classes = {
            NodeType.START: StartNodeData,
            NodeType.END: EndNodeData,
            NodeType.LLM: LLMNodeData,
            NodeType.TEMPLATE_TRANSFORM: TemplateTransformNodeData,
            NodeType.DATASET_RETRIEVAL: DatasetRetrievalNodeData,
            NodeType.CODE: CodeNodeData,
            NodeType.TOOL: ToolNodeData,
            NodeType.HTTP_REQUEST: HttpRequestNodeData,
        }

        # 6. Validate all nodes
        node_data_dict: dict[UUID, BaseNodeData] = {}
        start_nodes = 0
        end_nodes = 0
        for node in nodes:
            # 7. Each node must be a dict
            if not isinstance(node, dict):
                raise ValidateErrorException("Workflow node data type is invalid. Please verify and try again.")

            # 8. Determine node type and corresponding data class
            node_type = node.get("node_type", "")
            node_data_cls = node_data_classes.get(node_type, None)
            if not node_data_cls:
                raise ValidateErrorException("Workflow node type is invalid. Please verify and try again.")

            # 9. Instantiate and validate node via Pydantic
            node_data = node_data_cls(**node)

            # 10. Ensure exactly one START node and one END node
            if node_data.node_type == NodeType.START:
                if start_nodes >= 1:
                    raise ValidateErrorException("Workflow can contain only one START node.")
                start_nodes += 1
            elif node_data.node_type == NodeType.END:
                if end_nodes >= 1:
                    raise ValidateErrorException("Workflow can contain only one END node.")
                end_nodes += 1

            # 11. Node IDs must be unique
            if node_data.id in node_data_dict:
                raise ValidateErrorException("Workflow node id must be unique. Please verify and try again.")

            # 12. Node titles must be unique (after trimming spaces)
            if any(item.title.strip() == node_data.title.strip() for item in node_data_dict.values()):
                raise ValidateErrorException("Workflow node title must be unique. Please verify and try again.")

            # 13. Save node
            node_data_dict[node_data.id] = node_data

        # 14. Validate edges
        edge_data_dict: dict[UUID, BaseEdgeData] = {}
        for edge in edges:
            # 15. Each edge must be a dict
            if not isinstance(edge, dict):
                raise ValidateErrorException("Workflow edge data type is invalid. Please verify and try again.")

            # 16. Instantiate and validate edge via Pydantic
            edge_data = BaseEdgeData(**edge)

            # 17. Edge IDs must be unique
            if edge_data.id in edge_data_dict:
                raise ValidateErrorException("Workflow edge id must be unique. Please verify and try again.")

            # 18. Validate that edge endpoints exist and types match
            if (
                    edge_data.source not in node_data_dict
                    or edge_data.source_type != node_data_dict[edge_data.source].node_type
                    or edge_data.target not in node_data_dict
                    or edge_data.target_type != node_data_dict[edge_data.target].node_type
            ):
                raise ValidateErrorException(
                    "Workflow edge source/target node does not exist or has a mismatched type. "
                    "Please verify and try again."
                )

            # 19. Ensure each (source, target) pair is unique
            if any(
                    (item.source == edge_data.source and item.target == edge_data.target)
                    for item in edge_data_dict.values()
            ):
                raise ValidateErrorException("Duplicate workflow edge detected (same source and target).")

            # 20. Save edge
            edge_data_dict[edge_data.id] = edge_data

        # 21. Build adjacency structures
        adj_list = cls._build_adj_list(edge_data_dict.values())
        reverse_adj_list = cls._build_reverse_adj_list(edge_data_dict.values())
        in_degree, out_degree = cls._build_degrees(edge_data_dict.values())

        # 22. Check that there is exactly one graph-level START and END
        start_nodes = [node_data for node_data in node_data_dict.values() if in_degree[node_data.id] == 0]
        end_nodes = [node_data for node_data in node_data_dict.values() if out_degree[node_data.id] == 0]
        if (
                len(start_nodes) != 1
                or len(end_nodes) != 1
                or start_nodes[0].node_type != NodeType.START
                or end_nodes[0].node_type != NodeType.END
        ):
            raise ValidateErrorException(
                "The workflow graph must have exactly one START node and one END node as entry and exit points."
            )

        # 23. Get the unique start node
        start_node_data = start_nodes[0]

        # 24. Check connectivity (no unreachable nodes)
        if not cls._is_connected(adj_list, start_node_data.id):
            raise ValidateErrorException(
                "The workflow graph contains unreachable nodes (graph is not connected). Please verify and try again."
            )

        # 25. Detect cycles using Kahn's algorithm
        if cls._is_cycle(node_data_dict.values(), adj_list, in_degree):
            raise ValidateErrorException("The workflow graph contains a cycle. Please verify and try again.")

        # 26. Validate variable references across nodes
        cls._validate_inputs_ref(node_data_dict, reverse_adj_list)

        # 27. Replace raw dicts with validated node/edge objects in values
        values["nodes"] = list(node_data_dict.values())
        values["edges"] = list(edge_data_dict.values())

        return values

    @classmethod
    def _is_connected(cls, adj_list: defaultdict[Any, list], start_node_id: UUID) -> bool:
        """
        Check if the graph is connected from the given start node
        using BFS over the adjacency list.
        """
        # 1. Track visited nodes
        visited = set()

        # 2. Initialize queue with start node
        queue = deque([start_node_id])
        visited.add(start_node_id)

        # 3. BFS traversal
        while queue:
            node_id = queue.popleft()
            for neighbor in adj_list[node_id]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        # 4. If the number of visited nodes differs from number of keys in adj_list,
        #    then some nodes are not reachable.
        return len(visited) == len(adj_list)

    @classmethod
    def _is_cycle(
            cls,
            nodes: list[BaseNodeData],
            adj_list: defaultdict[Any, list],
            in_degree: defaultdict[Any, int],
    ) -> bool:
        """
        Detect whether the graph contains a cycle using Kahn's algorithm
        (topological sort). Returns True if a cycle exists, False otherwise.
        """
        # 1. Collect all nodes with in-degree 0
        zero_in_degree_nodes = deque([node.id for node in nodes if in_degree[node.id] == 0])

        # 2. Count visited nodes
        visited_count = 0

        # 3. Process nodes in topological order
        while zero_in_degree_nodes:
            # 4. Pop a node with in-degree 0
            node_id = zero_in_degree_nodes.popleft()
            visited_count += 1

            # 5. Decrease in-degree of neighbors
            for neighbor in adj_list[node_id]:
                in_degree[neighbor] -= 1

                # 6. When in-degree becomes 0, add neighbor to queue
                #    If there is a cycle, at least one node's in-degree will never drop to 0,
                #    so visited_count will be less than total nodes.
                if in_degree[neighbor] == 0:
                    zero_in_degree_nodes.append(neighbor)

        # 7. If we visited fewer nodes than exist, there must be a cycle
        return visited_count != len(nodes)

    @classmethod
    def _validate_inputs_ref(
            cls,
            node_data_dict: dict[UUID, BaseNodeData],
            reverse_adj_list: defaultdict[Any, list],
    ) -> None:
        """
        Validate that variable references between nodes are correct.

        - Referenced node must be in the predecessors of the current node.
        - Referenced variable name must exist in the referenced node's outputs
          (or inputs in case of START node).
        """
        # 1. Iterate over all nodes
        for node_data in node_data_dict.values():
            # 2. Collect all predecessors of this node
            predecessors = cls._get_predecessors(reverse_adj_list, node_data.id)

            # 3. START node has no inputs to validate
            if node_data.node_type != NodeType.START:
                # 4. Determine which variables to validate (inputs for most nodes, outputs for END node)
                variables: list[VariableEntity] = (
                    node_data.inputs if node_data.node_type != NodeType.END else node_data.outputs
                )

                # 5. Validate each variable
                for variable in variables:
                    # 6. Only validate reference-type variables
                    if variable.value.type == VariableValueType.REF:
                        # 7. The referenced node must be in the predecessors set
                        if (
                                len(predecessors) <= 0
                                or variable.value.content.ref_node_id not in predecessors
                        ):
                            raise ValidateErrorException(
                                f"Workflow node [{node_data.title}] has an invalid reference to a previous node."
                            )

                        # 8. Get the referenced node
                        ref_node_data = node_data_dict.get(variable.value.content.ref_node_id)

                        # 9. Determine the list of variables for the referenced node
                        ref_variables = (
                            ref_node_data.inputs
                            if ref_node_data.node_type == NodeType.START
                            else ref_node_data.outputs
                        )

                        # 10. Check that the referenced variable name exists in that list
                        if not any(
                                [ref_variable.name == variable.value.content.ref_var_name]
                                for ref_variable in ref_variables
                        ):
                            raise ValidateErrorException(
                                f"Workflow node [{node_data.title}] references a non-existent variable "
                                f"on the previous node. Please verify and try again."
                            )

    @classmethod
    def _build_adj_list(cls, edges: list[BaseEdgeData]) -> defaultdict[Any, list]:
        """
        Build adjacency list.

        Key: node id
        Value: list of directly connected successor node ids.
        """
        adj_list = defaultdict(list)
        for edge in edges:
            adj_list[edge.source].append(edge.target)
        return adj_list

    @classmethod
    def _build_reverse_adj_list(cls, edges: list[BaseEdgeData]) -> defaultdict[Any, list]:
        """
        Build reverse adjacency list.

        Key: node id
        Value: list of directly connected predecessor node ids.
        """
        reverse_adj_list = defaultdict(list)
        for edge in edges:
            reverse_adj_list[edge.target].append(edge.source)
        return reverse_adj_list

    @classmethod
    def _build_degrees(
            cls,
            edges: list[BaseEdgeData],
    ) -> tuple[defaultdict[Any, int], defaultdict[Any, int]]:
        """
        Compute in-degree and out-degree for each node, based on edges.

        in_degree: number of incoming edges per node.
        out_degree: number of outgoing edges per node.
        """
        in_degree = defaultdict(int)
        out_degree = defaultdict(int)

        for edge in edges:
            in_degree[edge.target] += 1
            out_degree[edge.source] += 1

        return in_degree, out_degree

    @classmethod
    def _get_predecessors(
            cls,
            reverse_adj_list: defaultdict[Any, list],
            target_node_id: UUID,
    ) -> list[UUID]:
        """
        Given a reverse adjacency list and a target node id, return
        all of its (direct and indirect) predecessor node ids.
        """
        visited = set()
        predecessors = []

        def dfs(node_id: UUID):
            """Depth-first search over predecessors."""
            if node_id not in visited:
                visited.add(node_id)
                predecessors.append(node_id)
                for neighbor in reverse_adj_list[node_id]:
                    dfs(neighbor)

        dfs(target_node_id)

        return predecessors


class WorkflowState(TypedDict):
    """
    Workflow graph state.

    - inputs: initial workflow inputs (tool inputs)
    - outputs: final workflow outputs (tool outputs)
    - node_results: execution results for each node
    """
    inputs: Annotated[dict[str, Any], _process_dict]
    outputs: Annotated[dict[str, Any], _process_dict]
    node_results: Annotated[list[NodeResult], _process_node_results]
