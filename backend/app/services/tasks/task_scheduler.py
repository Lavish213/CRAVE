from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

from app.services.tasks.task_state import TaskState, TaskStatus, utc_now
from app.services.tasks.task_registry import get_task_registry
from app.services.tasks.task_graph import get_task_graph


logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    Executes tasks respecting dependency graph and retry rules.

    This is a simple in-process scheduler used by pipeline runners.
    """

    def __init__(self) -> None:
        self.registry = get_task_registry()
        self.graph = get_task_graph()

        self._tasks: Dict[str, TaskState] = {}

    # -----------------------------------------------------
    # Task submission
    # -----------------------------------------------------

    def submit(self, task: TaskState) -> None:
        """
        Add a task to scheduler.
        """

        if task.task_id in self._tasks:
            raise ValueError(f"task already scheduled: {task.task_id}")

        self._tasks[task.task_id] = task

        task.mark_scheduled()

        logger.debug(
            "task_submitted id=%s type=%s",
            task.task_id,
            task.task_type,
        )

    # -----------------------------------------------------
    # Dependency checks
    # -----------------------------------------------------

    def _dependencies_satisfied(self, task: TaskState) -> bool:

        parents = self.graph.get_parents(task.task_type)

        if not parents:
            return True

        for parent_type in parents:

            parent_found = False

            for other in self._tasks.values():

                if other.task_type == parent_type:

                    parent_found = True

                    if other.status != TaskStatus.SUCCEEDED:
                        return False

            if not parent_found:
                return False

        return True

    # -----------------------------------------------------
    # Task selection
    # -----------------------------------------------------

    def _select_ready_tasks(self) -> List[TaskState]:

        ready: List[TaskState] = []

        for task in self._tasks.values():

            if not task.ready_to_run():
                continue

            if not self._dependencies_satisfied(task):
                continue

            ready.append(task)

        return ready

    # -----------------------------------------------------
    # Execution
    # -----------------------------------------------------

    def _execute(self, task: TaskState) -> None:

        handler = self.registry.get_handler(task.task_type)

        try:

            task.mark_running()

            logger.info(
                "task_started id=%s type=%s",
                task.task_id,
                task.task_type,
            )

            result = handler(task)

            if isinstance(result, dict):
                task.mark_succeeded(result=result)
            else:
                task.mark_succeeded()

            logger.info(
                "task_succeeded id=%s type=%s",
                task.task_id,
                task.task_type,
            )

        except Exception as exc:

            logger.exception(
                "task_failed id=%s type=%s",
                task.task_id,
                task.task_type,
            )

            task.mark_failed(
                code="task_execution_failed",
                message=str(exc),
                retryable=True,
            )

    # -----------------------------------------------------
    # Main loop
    # -----------------------------------------------------

    def run_once(self) -> None:
        """
        Run one scheduling cycle.
        """

        ready_tasks = self._select_ready_tasks()

        if not ready_tasks:
            return

        for task in ready_tasks:
            self._execute(task)

    # -----------------------------------------------------
    # Status helpers
    # -----------------------------------------------------

    def all_tasks(self) -> List[TaskState]:
        return list(self._tasks.values())

    def completed(self) -> List[TaskState]:
        return [
            t
            for t in self._tasks.values()
            if t.status == TaskStatus.SUCCEEDED
        ]

    def failed(self) -> List[TaskState]:
        return [
            t
            for t in self._tasks.values()
            if t.status == TaskStatus.DEAD
        ]

    def pending(self) -> List[TaskState]:
        return [
            t
            for t in self._tasks.values()
            if t.status not in {TaskStatus.SUCCEEDED, TaskStatus.DEAD}
        ]

    # -----------------------------------------------------
    # Diagnostics
    # -----------------------------------------------------

    def summary(self) -> Dict[str, int]:

        counts = {
            "total": len(self._tasks),
            "succeeded": 0,
            "failed": 0,
            "pending": 0,
        }

        for task in self._tasks.values():

            if task.status == TaskStatus.SUCCEEDED:
                counts["succeeded"] += 1
            elif task.status == TaskStatus.DEAD:
                counts["failed"] += 1
            else:
                counts["pending"] += 1

        return counts