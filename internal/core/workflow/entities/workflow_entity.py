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

# Workflow configuration validation settings
WORKFLOW_CONFIG_NAME_PATTERN = r'^[A-Za-z_][A-Za-z0-9_]*$'
WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH = 1024


def _process_dict(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Reducer function for workflow state dictionaries."""
    # 1. Handle cases where left or right is None/empty
    left = left or {}
    right = right or {}

    # 2. Merge and return the updated dictionary
    return {**left, **right}


def _process_node_results(left: list[NodeResult], right: list[NodeResult]) -> list[NodeResult]:
    """Reducer function for workflow node result lists."""
    # 1. Handle cases where left or right is None/empty
    left = left or []
    right = right or []

    # 2. Concatenate and return the updated list
    return left + right


class WorkflowConfig(BaseModel):
    """Workflow configuration information."""
    account_id: UUID  # Unique identifier of the user
    name: str = ""  # Workflow name, must be in English characters
    description: str = ""  # Workflow description, used to tell the LLM when to call this workflow
    nodes: list[BaseNodeData] = Field(default_factory=list)  # List of nodes in the workflow
    edges: list[BaseEdgeData] = Field(default_factory=list)  # List of edges in the workflow

    @root_validator(pre=True)
    def validate_workflow_config(cls, values: dict[str, Any]):
        """Custom validator for validating all parameters in the workflow configuration."""
        # 1. Get workflow name and validate it matches the pattern
        name = values.get("name", None)
        if not name or not re.match(WORKFLOW_CONFIG_NAME_PATTERN, name):
            raise ValidateErrorException(
                "Workflow name may only contain letters, digits, and underscores, "
                "and must start with a letter or underscore."
            )

        # 2. Validate workflow description, which is passed to the LLM; length must not exceed 1024 characters
        description = values.get("description", None)
        if not description or len(description) > WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH:
            raise ValidateErrorException(
                "Workflow description length must not exceed 1024 characters."
            )

        # 3. Get node and edge list information
        nodes = values.get("nodes", [])
        edges = values.get("edges", [])

        # 4. Validate that nodes/edges are lists and not empty
        if not isinstance(nodes, list) or len(nodes) <= 0:
            raise ValidateErrorException("Workflow node list is invalid. Please check and try again.")
        if not isinstance(edges, list) or len(edges) <= 0:
            raise ValidateErrorException("Workflow edge list is invalid. Please check and try again.")

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

        # 5. Iterate through all nodes
        node_data_dict: dict[UUID, BaseNodeData] = {}
        start_nodes = 0
        end_nodes = 0
        for node in nodes:
            # 6. Ensure each node is a dict
            if not isinstance(node, dict):
                raise ValidateErrorException("Workflow node data type is invalid. Please check and try again.")

            # 7. Get node type and ensure it exists
            node_type = node.get("node_type", "")
            node_data_cls = node_data_classes.get(node_type, None)
            if not node_data_cls:
                raise ValidateErrorException("Workflow node type is invalid. Please check and try again.")

            # 8. Instantiate node data and let BaseModel perform validation
            node_data = node_data_cls(**node)

            # 9. Check uniqueness of start and end nodes
            if node_data.node_type == NodeType.START:
                if start_nodes >= 1:
                    raise ValidateErrorException("There can be only one START node in the workflow.")
                start_nodes += 1
            elif node_data.node_type == NodeType.END:
                if end_nodes >= 1:
                    raise ValidateErrorException("There can be only one END node in the workflow.")
                end_nodes += 1

            # 10. Ensure node IDs are unique
            if node_data.id in node_data_dict:
                raise ValidateErrorException("Workflow node IDs must be unique. Please check and try again.")

            # 11. Ensure node titles are unique
            if any(item.title.strip() == node_data.title.strip() for item in node_data_dict.values()):
                raise ValidateErrorException("Workflow node titles must be unique. Please check and try again.")

            # 12. Add node data to node_data_dict
            node_data_dict[node_data.id] = node_data

        # 13. Iterate through edges
        edge_data_dict: dict[UUID, BaseEdgeData] = {}
        for edge in edges:
            # 14. Ensure edge is a dict
            if not isinstance(edge, dict):
                raise ValidateErrorException("Workflow edge data type is invalid. Please check and try again.")

            # 15. Instantiate edge data and let BaseModel perform validation
            edge_data = BaseEdgeData(**edge)

            # 16. Ensure edge IDs are unique
            if edge_data.id in edge_data_dict:
                raise ValidateErrorException("Workflow edge IDs must be unique. Please check and try again.")

            # 17. Validate that edge's source/target/source_type/target_type match nodes
            if (
                    edge_data.source not in node_data_dict
                    or edge_data.source_type != node_data_dict[edge_data.source].node_type
                    or edge_data.target not in node_data_dict
                    or edge_data.target_type != node_data_dict[edge_data.target].node_type
            ):
                raise ValidateErrorException(
                    "Workflow edge source/target does not match existing nodes or has an incorrect type. "
                    "Please check and try again."
                )

            # 18. Ensure edges are unique (source+target combination must be unique)
            if any(
                    (item.source == edge_data.source and item.target == edge_data.target)
                    for item in edge_data_dict.values()
            ):
                raise ValidateErrorException("Duplicate workflow edge detected. Please check and try again.")

            # 19. After basic validation passes, add edge data to edge_data_dict
            edge_data_dict[edge_data.id] = edge_data

        # 20. Build adjacency list, reverse adjacency list, in-degree and out-degree
        adj_list = cls._build_adj_list(edge_data_dict.values())
        reverse_adj_list = cls._build_reverse_adj_list(edge_data_dict.values())
        in_degree, out_degree = cls._build_degrees(edge_data_dict.values())

        # 21. From edges, validate there is exactly one start and one end node
        #     (nodes with in_degree == 0 are starts, out_degree == 0 are ends)
        start_nodes = [node_data for node_data in node_data_dict.values() if in_degree[node_data.id] == 0]
        end_nodes = [node_data for node_data in node_data_dict.values() if out_degree[node_data.id] == 0]
        if (
                len(start_nodes) != 1
                or len(end_nodes) != 1
                or start_nodes[0].node_type != NodeType.START
                or end_nodes[0].node_type != NodeType.END
        ):
            raise ValidateErrorException(
                "The workflow must have exactly one START and one END node as the entry and exit of the graph."
            )

        # 22. Get the unique start node
        start_node_data = start_nodes[0]

        # 23. Use edge information to verify graph connectivity and ensure no isolated nodes exist
        if not cls._is_connected(adj_list, start_node_data.id):
            raise ValidateErrorException(
                "The workflow contains unreachable nodes. The graph is not connected. Please check and try again."
            )

        # 24. Check whether there is a cycle in edges (i.e., cyclic graph structure)
        if cls._is_cycle(node_data_dict.values(), adj_list, in_degree):
            raise ValidateErrorException("The workflow contains cycles. Please check and try again.")

        # 25. Validate that input/output references in nodes and edges are correct
        cls._validate_inputs_ref(node_data_dict, reverse_adj_list)

        # 26. Update values
        values["nodes"] = list(node_data_dict.values())
        values["edges"] = list(edge_data_dict.values())

        return values

    @classmethod
    def _is_connected(cls, adj_list: defaultdict[Any, list], start_node_id: UUID) -> bool:
        """Check if the graph is connected via BFS, starting from the given start node ID."""
        # 1. Track visited nodes
        visited = set()

        # 2. Create a deque and enqueue the start node
        queue = deque([start_node_id])
        visited.add(start_node_id)

        # 3. BFS traversal over children of each node
        while queue:
            node_id = queue.popleft()
            for neighbor in adj_list[node_id]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        # 4. Check whether the number of visited nodes equals the total number of nodes in adj_list.
        #    If not, there are isolated nodes and the graph is not connected.
        return len(visited) == len(adj_list)

    @classmethod
    def _is_cycle(
            cls,
            nodes: list[BaseNodeData],
            adj_list: defaultdict[Any, list],
            in_degree: defaultdict[Any, int],
    ) -> bool:
        """
        Use topological sorting (Kahn's algorithm) with the given node list, adjacency list,
        and in-degree data to check whether the graph contains a cycle.
        Returns True if a cycle exists, otherwise False.
        """
        # 1. Collect all nodes with zero in-degree (start nodes)
        zero_in_degree_nodes = deque([node.id for node in nodes if in_degree[node.id] == 0])

        # 2. Count of visited nodes
        visited_count = 0

        # 3. Iterate over nodes with zero in-degree
        while zero_in_degree_nodes:
            # 4. Pop a zero in-degree node from the deque and increment visited count
            node_id = zero_in_degree_nodes.popleft()
            visited_count += 1

            # 5. Traverse all child nodes of the current node
            for neighbor in adj_list[node_id]:
                # 6. Decrease the in-degree of each child node by 1
                in_degree[neighbor] -= 1

                # 7. Core idea of Kahn's algorithm:
                #    If a cycle exists, at least one non-terminal node will have in-degree >= 2
                #    and its in-degree can never be reduced to 0, which prevents it and its
                #    descendants from being visited. Then visited_count will be less than total nodes.
                if in_degree[neighbor] == 0:
                    zero_in_degree_nodes.append(neighbor)

        # 8. If visited_count != total nodes, a cycle exists
        return visited_count != len(nodes)

    @classmethod
    def _validate_inputs_ref(
            cls,
            node_data_dict: dict[UUID, BaseNodeData],
            reverse_adj_list: defaultdict[Any, list],
    ) -> None:
        """Validate that all input references are correct; raise an exception if anything is invalid."""
        # 1. Iterate through all nodes
        for node_data in node_data_dict.values():
            # 2. Get all predecessors of the current node
            predecessors = cls._get_predecessors(reverse_adj_list, node_data.id)

            # 3. If the node is not a START node, validate its input references
            if node_data.node_type != NodeType.START:
                # 4. Based on node type, get variables to validate either from inputs or outputs
                variables: list[VariableEntity] = (
                    node_data.inputs if node_data.node_type != NodeType.END
                    else node_data.outputs
                )

                # 5. Iterate through all variables to validate
                for variable in variables:
                    # 6. Only validate variables of type REF
                    if variable.value.type == VariableValueType.REF:
                        # 7. If there are no predecessors, or the referenced node is not among predecessors,
                        #    raise an error
                        if (
                                len(predecessors) <= 0
                                or variable.value.content.ref_node_id not in predecessors
                        ):
                            raise ValidateErrorException(
                                f"Workflow node [{node_data.title}] has an invalid data reference. "
                                "Please check and try again."
                            )

                        # 8. Get the referenced predecessor node
                        ref_node_data = node_data_dict.get(variable.value.content.ref_node_id)

                        # 9. Get the list of variables from the referenced node:
                        #    if it's a START node, use inputs; otherwise, use outputs
                        ref_variables = (
                            ref_node_data.inputs if ref_node_data.node_type == NodeType.START
                            else ref_node_data.outputs
                        )

                        # 10. Confirm that the referenced variable name exists in the referenced node
                        if not any(
                                ref_variable.name == variable.value.content.ref_var_name
                                for ref_variable in ref_variables
                        ):
                            raise ValidateErrorException(
                                f"Workflow node [{node_data.title}] references a non-existent node variable. "
                                "Please check and try again."
                            )

    @classmethod
    def _build_adj_list(cls, edges: list[BaseEdgeData]) -> defaultdict[Any, list]:
        """Build an adjacency list where the key is the node ID and the value is the list of direct child nodes."""
        adj_list = defaultdict(list)
        for edge in edges:
            adj_list[edge.source].append(edge.target)
        return adj_list

    @classmethod
    def _build_reverse_adj_list(cls, edges: list[BaseEdgeData]) -> defaultdict[Any, list]:
        """Build a reverse adjacency list where the key is the node ID and the value is the list of direct parent nodes."""
        reverse_adj_list = defaultdict(list)
        for edge in edges:
            reverse_adj_list[edge.target].append(edge.source)
        return reverse_adj_list

    @classmethod
    def _build_degrees(cls, edges: list[BaseEdgeData]) -> tuple[defaultdict[Any, int], defaultdict[Any, int]]:
        """
        Compute the in-degree and out-degree for each node based on the given edges.

        in_degree:  number of nodes pointing to this node
        out_degree: number of nodes this node points to
        """
        in_degree = defaultdict(int)
        out_degree = defaultdict(int)

        for edge in edges:
            in_degree[edge.target] += 1
            out_degree[edge.source] += 1

        return in_degree, out_degree

    @classmethod
    def _get_predecessors(cls, reverse_adj_list: defaultdict[Any, list], target_node_id: UUID) -> list[UUID]:
        """Get all predecessor nodes of the target node ID using the reverse adjacency list."""
        visited = set()
        predecessors = []

        def dfs(node_id):
            """Traverse all predecessor nodes using DFS."""
            if node_id not in visited:
                visited.add(node_id)
                if node_id != target_node_id:
                    predecessors.append(node_id)
                for neighbor in reverse_adj_list[node_id]:
                    dfs(neighbor)

        dfs(target_node_id)

        return predecessors


class WorkflowState(TypedDict):
    """Workflow graph runtime state dictionary."""
    # Initial inputs of the workflow (tool inputs)
    inputs: Annotated[dict[str, Any], _process_dict]
    # Final outputs of the workflow (tool outputs)
    outputs: Annotated[dict[str, Any], _process_dict]
    # Execution results of each node
    node_results: Annotated[list[NodeResult], _process_node_results]
