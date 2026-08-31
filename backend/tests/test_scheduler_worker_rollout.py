from __future__ import annotations

import pytest

from app.scheduler import SCHEDULER_JOB_IDS, create_scheduler
from app.scheduler_worker import configured_job_allowlist, create_worker_scheduler


def test_standalone_worker_is_default_off(monkeypatch):
    monkeypatch.setattr("app.scheduler_worker.settings.scheduler_worker_enabled", False)
    monkeypatch.setattr("app.scheduler_worker.settings.scheduler_job_allowlist", "")

    assert create_worker_scheduler() is None


def test_worker_registers_only_explicitly_allowed_jobs(monkeypatch):
    monkeypatch.setattr("app.scheduler_worker.settings.scheduler_worker_enabled", True)
    monkeypatch.setattr(
        "app.scheduler_worker.settings.scheduler_job_allowlist",
        "share_parser,image_processing_recovery",
    )

    scheduler = create_worker_scheduler()

    assert scheduler is not None
    assert {job.id for job in scheduler.get_jobs()} == {
        "share_parser",
        "image_processing_recovery",
    }


def test_worker_refuses_enabled_empty_allowlist(monkeypatch):
    monkeypatch.setattr("app.scheduler_worker.settings.scheduler_worker_enabled", True)
    monkeypatch.setattr("app.scheduler_worker.settings.scheduler_job_allowlist", "")

    with pytest.raises(RuntimeError, match="allowlist is empty"):
        create_worker_scheduler()


def test_worker_refuses_unknown_job_id(monkeypatch):
    monkeypatch.setattr("app.scheduler_worker.settings.scheduler_worker_enabled", True)
    monkeypatch.setattr(
        "app.scheduler_worker.settings.scheduler_job_allowlist",
        "share_parser,typo_job",
    )

    with pytest.raises(RuntimeError, match="Unknown scheduler job IDs: typo_job"):
        create_worker_scheduler()


def test_allowlist_parser_trims_and_deduplicates():
    assert configured_job_allowlist(" share_parser,share_parser, ranking_update ") == {
        "share_parser",
        "ranking_update",
    }


def test_embedded_scheduler_still_registers_all_jobs_by_default():
    scheduler = create_scheduler()

    assert {job.id for job in scheduler.get_jobs()} == set(SCHEDULER_JOB_IDS)
