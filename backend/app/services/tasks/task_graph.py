from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Dict, Iterable, List, Set


logger = logging.getLogger(__name__)


class TaskGraph:
    """
    Directed acyclic graph (DAG) describing task dependencies.

    Example:
        crawl_site -> extract_menu -> normalize_menu -> canonicalize_menu
    """

    def __init__(self) -> None:
        self._edges: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_edges: Dict[str, Set[str]] = defaultdict(set)

    # -----------------------------------------------------
    # Graph building
    # -----------------------------------------------------

    def add_dependency(self, parent: str, child: str) -> None:
        """
        parent -> child
        child cannot run until parent completes
        """

        if parent == child:
            raise ValueError("task cannot depend on itself")

        self._edges[parent].add(child)
        self._reverse_edges[child].add(parent)

        logger.debug(
            "task_dependency_added parent=%s child=%s",
            parent,
            child,
        )

    def add_dependencies(self, parent: str, children: Iterable[str]) -> None:
        for child in children:
            self.add_dependency(parent, child)

    # -----------------------------------------------------
    # Queries
    # -----------------------------------------------------

    def get_children(self, task_type: str) -> List[str]:
        return list(self._edges.get(task_type, set()))

    def get_parents(self, task_type: str) -> List[str]:
        return list(self._reverse_edges.get(task_type, set()))

    def has_dependencies(self, task_type: str) -> bool:
        return task_type in self._reverse_edges

    # -----------------------------------------------------
    # Execution planning
    # -----------------------------------------------------

    def topological_order(self) -> List[str]:
        """
        Return tasks in safe execution order.
        """

        in_degree: Dict[str, int] = defaultdict(int)

        nodes: Set[str] = set(self._edges.keys()) | set(self._reverse_edges.keys())

        for child, parents in self._reverse_edges.items():
            in_degree[child] = len(parents)

        queue = deque()

        for node in nodes:
            if in_degree[node] == 0:
                queue.append(node)

        order: List[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)

            for child in self._edges.get(node, []):
                in_degree[child] -= 1

                if in_degree[child] == 0:
                    queue.append(child)

        if len(order) != len(nodes):
            raise RuntimeError("task_graph_cycle_detected")

        return order

    # -----------------------------------------------------
    # Cycle detection
    # -----------------------------------------------------

    def validate_no_cycles(self) -> None:
        """
        Raises if a cycle exists.
        """

        self.topological_order()

    # -----------------------------------------------------
    # Diagnostics
    # -----------------------------------------------------

    def describe(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Return dependency structure for debugging.
        """

        result: Dict[str, Dict[str, List[str]]] = {}

        nodes = set(self._edges.keys()) | set(self._reverse_edges.keys())

        for node in nodes:
            result[node] = {
                "parents": list(self._reverse_edges.get(node, [])),
                "children": list(self._edges.get(node, [])),
            }

        return result


# ---------------------------------------------------------
# Global graph
# ---------------------------------------------------------

_graph: TaskGraph | None = None


def get_task_graph() -> TaskGraph:
    global _graph

    if _graph is None:
        _graph = TaskGraph()

    return _graph