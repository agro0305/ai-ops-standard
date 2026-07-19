from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "retention.py"
SPEC = importlib.util.spec_from_file_location("aiops_retention", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def make_old(path: Path, days: int, now: float) -> None:
    timestamp = now - days * 86400
    os.utime(path, (timestamp, timestamp))


def test_retention_plans_only_expired_backups_and_rotated_audit(tmp_path):
    current = time.time()
    backup_root = tmp_path / ".aiops-backups"
    backup_root.mkdir()
    old_backup = backup_root / "old-plan"
    old_backup.mkdir()
    (old_backup / "backup-manifest.json").write_text("{}", encoding="utf-8")
    new_backup = backup_root / "new-plan"
    new_backup.mkdir()
    make_old(old_backup, 40, current)

    audit_root = tmp_path / ".aiops-audit"
    audit_root.mkdir()
    current_audit = audit_root / "events.jsonl"
    current_audit.write_text("{}\n", encoding="utf-8")
    old_rotation = audit_root / "events.jsonl.1"
    old_rotation.write_text("{}\n", encoding="utf-8")
    make_old(old_rotation, 100, current)

    plan = MODULE.plan_retention(
        tmp_path,
        backup_days=30,
        audit_days=90,
        current_time=current,
    )
    names = {item["path"] for item in plan["candidates"]}
    assert ".aiops-backups/old-plan" in names
    assert ".aiops-audit/events.jsonl.1" in names
    assert ".aiops-backups/new-plan" not in names
    assert ".aiops-audit/events.jsonl" not in names


def test_retention_apply_deletes_only_planned_candidates(tmp_path):
    current = time.time()
    backup_root = tmp_path / ".aiops-backups"
    backup_root.mkdir()
    old_backup = backup_root / "old-plan"
    old_backup.mkdir()
    (old_backup / "file.txt").write_text("data", encoding="utf-8")
    new_backup = backup_root / "new-plan"
    new_backup.mkdir()
    make_old(old_backup, 40, current)

    plan = MODULE.plan_retention(
        tmp_path,
        backup_days=30,
        audit_days=90,
        current_time=current,
    )
    result = MODULE.apply_retention(plan)
    assert result["success"] is True
    assert result["deleted"] == 1
    assert not old_backup.exists()
    assert new_backup.exists()


def test_retention_rejects_zero_day_policy(tmp_path):
    try:
        MODULE.plan_retention(tmp_path, backup_days=0, audit_days=90)
    except ValueError:
        pass
    else:
        raise AssertionError("zero-day retention must fail")
