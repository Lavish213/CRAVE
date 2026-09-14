# app/db/models/admin_audit_log.py
"""
A minimal, append-only log of admin/moderation actions -- who did what to
which report/submission, and when.

app/api/v1/routes/moderation.py (and menu_submissions.py's review endpoint)
correctly restrict *who* can act via the ADMIN_USER_IDS allowlist
(require_admin), but until this existed there was no persistent, queryable
record of *what* an admin actually did -- only ad-hoc log lines that scroll
out of any log retention window. This table is written alongside those log
lines, not instead of them: it's for "show me every action admin X took" /
"what happened to report Y", not for debugging.

Deliberately no `resolved`/`note`/`updated_at` fields -- unlike PlaceReport
or MenuSubmission, a row here is never mutated after it's written. It
records a fact about an action that already happened; correcting course
means writing a new row (e.g. a later re-review), not editing an old one.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, utcnow


class AdminAuditLog(Base):
    """
    One row per admin action, e.g. `action="approve_image_report"`,
    `target_type="image"`, `target_id=<image_id>`.
    """

    __tablename__ = "admin_audit_logs"

    __table_args__ = (
        Index("ix_admin_audit_logs_admin_user_id", "admin_user_id"),
        Index("ix_admin_audit_logs_target", "target_type", "target_id"),
        Index("ix_admin_audit_logs_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # The admin who performed the action (same identity space as
    # get_current_user_id / ADMIN_USER_IDS -- not a FK since users aren't
    # backed by their own table in this schema).
    admin_user_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # e.g. "approve_image_report", "reject_video_report",
    # "approve_menu_submission", "resolve_place_report".
    action: Mapped[str] = mapped_column(String(64), nullable=False)

    # e.g. "image", "video", "place_report", "menu_submission".
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # The id of whatever `target_type` names -- not a FK on purpose: it
    # points at different tables depending on target_type, and the audit
    # row should outlive the thing it describes (e.g. a later hard delete)
    # rather than being cascade-deleted with it.
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
