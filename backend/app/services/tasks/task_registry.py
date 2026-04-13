from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Type

from app.services.tasks.task_state import TaskState


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Task Handler Types
# ---------------------------------------------------------

TaskHandler = Callable[[TaskState], Any]


# ---------------------------------------------------------
# Registry
# ---------------------------------------------------------

class TaskRegistry:
    """
    Central registry for all task types and their handlers.

    Responsibilities:
        - register task handlers
        - validate task types
        - provide lookup for scheduler / workers
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, TaskHandler] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    # -----------------------------------------------------
    # Registration
    # -----------------------------------------------------

    def register(
        self,
        task_type: str,
        handler: TaskHandler,
        *,
        description: Optional[str] = None,
        max_attempts: Optional[int] = None,
    ) -> None:
        """
        Register a task handler.
        """

        if not task_type:
            raise ValueError("task_type must be provided")

        if task_type in self._handlers:
            raise ValueError(f"task already registered: {task_type}")

        self._handlers[task_type] = handler

        self._metadata[task_type] = {
            "description": description,
            "max_attempts": max_attempts,
        }

        logger.info(
            "task_registered type=%s description=%s",
            task_type,
            description,
        )

    # -----------------------------------------------------
    # Lookup
    # -----------------------------------------------------

    def get_handler(self, task_type: str) -> TaskHandler:
        """
        Retrieve handler for a task.
        """

        handler = self._handlers.get(task_type)

        if not handler:
            raise KeyError(f"no handler registered for task: {task_type}")

        return handler

    def has_handler(self, task_type: str) -> bool:
        return task_type in self._handlers

    # -----------------------------------------------------
    # Metadata
    # -----------------------------------------------------

    def get_metadata(self, task_type: str) -> Dict[str, Any]:
        return self._metadata.get(task_type, {})

    # -----------------------------------------------------
    # Introspection
    # -----------------------------------------------------

    def list_task_types(self) -> List[str]:
        return list(self._handlers.keys())

    def describe(self) -> Dict[str, Dict[str, Any]]:
        """
        Return registry information for debugging / diagnostics.
        """

        info: Dict[str, Dict[str, Any]] = {}

        for task_type, handler in self._handlers.items():
            meta = self._metadata.get(task_type, {})

            info[task_type] = {
                "handler": handler.__name__,
                "description": meta.get("description"),
                "max_attempts": meta.get("max_attempts"),
            }

        return info


# ---------------------------------------------------------
# Global Registry Instance
# ---------------------------------------------------------

_registry: Optional[TaskRegistry] = None


def get_task_registry() -> TaskRegistry:
    global _registry

    if _registry is None:
        _registry = TaskRegistry()

    return _registry


# ---------------------------------------------------------
# Decorator Helper
# ---------------------------------------------------------

def task(
    task_type: str,
    *,
    description: Optional[str] = None,
    max_attempts: Optional[int] = None,
) -> Callable[[TaskHandler], TaskHandler]:
    """
    Decorator for registering task handlers.

    Example:

        @task("website_discovery")
        def run_website_discovery(task_state):
            ...
    """

    def decorator(func: TaskHandler) -> TaskHandler:
        registry = get_task_registry()

        registry.register(
            task_type,
            func,
            description=description,
            max_attempts=max_attempts,
        )

        return func

    return decorator