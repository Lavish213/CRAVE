from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


# ---------------------------------------------------------
# Utilities
# ---------------------------------------------------------

def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------
# Status Enum
# ---------------------------------------------------------

class TaskStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD = "dead"


# ---------------------------------------------------------
# Task State
# ---------------------------------------------------------

class TaskState:
    """
    Tracks the lifecycle state of a single task execution.
    """

    def __init__(
        self,
        *,
        task_type: str,
        payload: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        max_attempts: int = 3,
    ) -> None:
        self.task_id: str = task_id or str(uuid.uuid4())
        self.task_type: str = task_type
        self.payload: Dict[str, Any] = payload or {}
        self.max_attempts: int = max_attempts

        self.status: TaskStatus = TaskStatus.PENDING
        self.attempt: int = 0

        self.result: Optional[Dict[str, Any]] = None
        self.error_code: Optional[str] = None
        self.error_message: Optional[str] = None

        self.created_at: datetime = utc_now()
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None

    # --------------------------------------------------
    # Lifecycle transitions
    # --------------------------------------------------

    def mark_scheduled(self) -> None:
        self.status = TaskStatus.SCHEDULED

    def mark_running(self) -> None:
        self.status = TaskStatus.RUNNING
        self.attempt += 1
        self.started_at = utc_now()

    def mark_succeeded(self, *, result: Optional[Dict[str, Any]] = None) -> None:
        self.status = TaskStatus.SUCCEEDED
        self.result = result
        self.finished_at = utc_now()

    def mark_failed(
        self,
        *,
        code: str,
        message: str,
        retryable: bool = True,
    ) -> None:
        self.error_code = code
        self.error_message = message
        self.finished_at = utc_now()

        if retryable and self.attempt < self.max_attempts:
            self.status = TaskStatus.FAILED
        else:
            self.status = TaskStatus.DEAD

    # --------------------------------------------------
    # Scheduler helpers
    # --------------------------------------------------

    def ready_to_run(self) -> bool:
        return self.status in {TaskStatus.PENDING, TaskStatus.SCHEDULED, TaskStatus.FAILED}

    # --------------------------------------------------
    # Serialization
    # --------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "result": self.result,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }
