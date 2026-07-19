from __future__ import annotations

import importlib.util
import json
import os
from argparse import Namespace
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[2] / "implementations" / "operations" / "aiops_operations.py"
SPEC = importlib.util.spec_from_file_location("aiops_operations", MODULE_PATH)
OPS = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(OPS)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def plan_args(discovery: Path, request: Path, output: Path) -> Namespace:
    return Namespace(discovery=str(discovery), request=str(request), output=str(output))


def backup_args(plan: Path, root: Path, replace: bool = False) -> Namespace:
    return Namespace(plan=str(plan), backup_root=str(root), replace=replace)


def execute_args(
    plan: Path,
    output: Path,
    *,
    manifest: Path | None = None,
    apply: bool = False,
    approved: bool = False,
) -> Namespace:
    return Namespace(
        plan=str(plan),
        manifest=str(manifest) if manifest else None,
        output=str(output),
        apply=apply,
        approved=approved,
        manual_preconditions_confirmed=False,
        continue_on_error=False,
    )


def rollback_args(
    plan: Path,
    manifest: Path,
    output: Path,
    *,
    execution_report: Path | None = None,
    apply: bool = False,
    approved: bool = False,
) -> Namespace:
    return Namespace(
        plan=str(plan),
        manifest=str(manifest),
        execution_report=str(execution_report) if execution_report else None,
        output=str(output),
        apply=apply,
        approved=approved,
        continue_on_error=False,
    )


def test_risk_classification():
    assert OPS.classify_risk([{"type": "write_file", "path": "/tmp/x"}]) == "low"
    assert OPS.classify_risk([{"type": "write_file", "path": "/etc/x"}]) == "high"
    assert OPS.classify_risk([{"type": "delete", "path": "/tmp/x"}]) == "high"
    assert OPS.classify_risk(
        [{"type": "write_file", "path": "/tmp/x", "safety_critical": True}]
    ) == "critical"


def test_plan_backup_execute_verify_and_rollback(tmp_path: Path):
    target = tmp_path / "target.txt"
    target.write_text("before\n", encoding="utf-8")
    discovery = tmp_path / "discovery.json"
    request = tmp_path / "request.json"
    plan_path = tmp_path / "plan.json"
    write_json(discovery, {"host": {"hostname": "test"}})
    write_json(
        request,
        {
            "plan_id": "test-plan",
            "intent": "test operation",
            "actions": [
                {"type": "write_file", "path": str(target), "content": "after\n"}
            ],
            "verification": [
                {"type": "file_contains", "path": str(target), "text": "after"}
            ],
        },
    )

    assert OPS.make_plan(plan_args(discovery, request, plan_path)) == 0
    plan = json.loads(plan_path.read_text())
    assert plan["risk"]["level"] == "low"
    assert plan["backup"]["required"] is True

    backup_root = tmp_path / "backups"
    assert OPS.make_backup(backup_args(plan_path, backup_root)) == 0
    manifest = backup_root / "test-plan" / "backup-manifest.json"
    assert manifest.exists()

    execution = tmp_path / "execution.json"
    with pytest.raises(PermissionError):
        OPS.execute(execute_args(plan_path, execution, apply=True))

    assert OPS.execute(
        execute_args(plan_path, execution, manifest=manifest, apply=True)
    ) == 0
    assert target.read_text() == "after\n"
    execution_data = json.loads(execution.read_text())
    assert execution_data["backup_verified"] is True
    assert "content" not in execution_data["results"][0]["action"]

    verification = tmp_path / "verification.json"
    assert OPS.verify(Namespace(plan=str(plan_path), output=str(verification))) == 0
    assert json.loads(verification.read_text())["passed"] is True

    rollback_report = tmp_path / "rollback.json"
    assert OPS.rollback(
        rollback_args(plan_path, manifest, rollback_report, apply=False)
    ) == 0
    assert target.read_text() == "after\n"
    assert json.loads(rollback_report.read_text())["apply"] is False

    assert OPS.rollback(
        rollback_args(plan_path, manifest, rollback_report, apply=True)
    ) == 0
    assert target.read_text() == "before\n"


def test_mkdir_and_new_file_are_removed_by_rollback(tmp_path: Path):
    directory = tmp_path / "created"
    target = directory / "status.txt"
    discovery = tmp_path / "discovery.json"
    request = tmp_path / "request.json"
    plan = tmp_path / "plan.json"
    write_json(discovery, {"host": {}})
    write_json(
        request,
        {
            "plan_id": "mkdir-plan",
            "actions": [
                {"type": "mkdir", "path": str(directory)},
                {"type": "write_file", "path": str(target), "content": "created"},
            ],
        },
    )
    assert OPS.make_plan(plan_args(discovery, request, plan)) == 0
    backup_root = tmp_path / "backups"
    assert OPS.make_backup(backup_args(plan, backup_root)) == 0
    manifest = backup_root / "mkdir-plan" / "backup-manifest.json"
    manifest_data = json.loads(manifest.read_text())
    assert sorted(entry["source"] for entry in manifest_data["entries"]) == sorted(
        [str(directory), str(target)]
    )
    assert all(entry["existed"] is False for entry in manifest_data["entries"])

    execution = tmp_path / "execution.json"
    assert OPS.execute(
        execute_args(plan, execution, manifest=manifest, apply=True)
    ) == 0
    assert target.exists()

    rollback = tmp_path / "rollback.json"
    assert OPS.rollback(rollback_args(plan, manifest, rollback, apply=True)) == 0
    assert not directory.exists()


def test_dry_run_does_not_require_approval_or_manifest(tmp_path: Path):
    target = tmp_path / "target.txt"
    plan = tmp_path / "plan.json"
    write_json(
        plan,
        {
            "plan_id": "dry-run",
            "risk": {"level": "high", "approval_required": True},
            "preconditions": [],
            "actions": [{"type": "delete", "path": str(target)}],
            "backup": {"required": True, "targets": [str(target)]},
            "verification": [],
        },
    )
    output = tmp_path / "execution.json"
    assert OPS.execute(execute_args(plan, output, apply=False, approved=False)) == 0
    assert not target.exists()
    assert json.loads(output.read_text())["results"][0]["status"] == "planned"


def test_high_risk_apply_requires_approval(tmp_path: Path):
    target = tmp_path / "target.txt"
    plan = tmp_path / "plan.json"
    write_json(
        plan,
        {
            "plan_id": "high-risk",
            "risk": {"level": "high", "approval_required": True},
            "preconditions": [],
            "actions": [{"type": "delete", "path": str(target)}],
            "backup": {"required": True, "targets": [str(target)]},
            "verification": [],
        },
    )
    with pytest.raises(PermissionError):
        OPS.execute(execute_args(plan, tmp_path / "out.json", apply=True))


def test_plan_change_after_backup_is_rejected(tmp_path: Path):
    target = tmp_path / "target.txt"
    target.write_text("before", encoding="utf-8")
    discovery = tmp_path / "discovery.json"
    request = tmp_path / "request.json"
    plan = tmp_path / "plan.json"
    write_json(discovery, {"host": {}})
    write_json(
        request,
        {
            "plan_id": "changed-plan",
            "actions": [
                {"type": "write_file", "path": str(target), "content": "after"}
            ],
        },
    )
    OPS.make_plan(plan_args(discovery, request, plan))
    backup_root = tmp_path / "backups"
    OPS.make_backup(backup_args(plan, backup_root))
    manifest = backup_root / "changed-plan" / "backup-manifest.json"

    changed = json.loads(plan.read_text())
    changed["actions"][0]["content"] = "tampered"
    write_json(plan, changed)
    with pytest.raises(PermissionError, match="plan changed"):
        OPS.execute(
            execute_args(
                plan, tmp_path / "execution.json", manifest=manifest, apply=True
            )
        )
    assert target.read_text() == "before"


def test_tampered_backup_object_is_rejected(tmp_path: Path):
    target = tmp_path / "target.txt"
    target.write_text("before", encoding="utf-8")
    discovery = tmp_path / "discovery.json"
    request = tmp_path / "request.json"
    plan = tmp_path / "plan.json"
    write_json(discovery, {"host": {}})
    write_json(
        request,
        {
            "plan_id": "tampered-backup",
            "actions": [
                {"type": "write_file", "path": str(target), "content": "after"}
            ],
        },
    )
    OPS.make_plan(plan_args(discovery, request, plan))
    backup_root = tmp_path / "backups"
    OPS.make_backup(backup_args(plan, backup_root))
    manifest = backup_root / "tampered-backup" / "backup-manifest.json"
    manifest_data = json.loads(manifest.read_text())
    Path(manifest_data["entries"][0]["backup"]).write_text("tampered", encoding="utf-8")

    with pytest.raises(PermissionError, match="digest mismatch"):
        OPS.execute(
            execute_args(
                plan, tmp_path / "execution.json", manifest=manifest, apply=True
            )
        )
    assert target.read_text() == "before"


def test_command_requires_explicit_rollback_argv(tmp_path: Path):
    discovery = tmp_path / "discovery.json"
    request = tmp_path / "request.json"
    write_json(discovery, {"host": {}})
    write_json(
        request,
        {
            "plan_id": "command-plan",
            "actions": [{"type": "command", "argv": ["true"]}],
        },
    )
    with pytest.raises(ValueError, match="rollback_argv"):
        OPS.make_plan(plan_args(discovery, request, tmp_path / "plan.json"))


def test_symlink_write_is_refused_without_explicit_replacement(tmp_path: Path):
    real = tmp_path / "real.txt"
    real.write_text("original", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlinks are unavailable")

    discovery = tmp_path / "discovery.json"
    request = tmp_path / "request.json"
    plan = tmp_path / "plan.json"
    write_json(discovery, {"host": {}})
    write_json(
        request,
        {
            "plan_id": "symlink-plan",
            "actions": [
                {"type": "write_file", "path": str(link), "content": "changed"}
            ],
        },
    )
    OPS.make_plan(plan_args(discovery, request, plan))
    backup_root = tmp_path / "backups"
    OPS.make_backup(backup_args(plan, backup_root))
    manifest = backup_root / "symlink-plan" / "backup-manifest.json"
    execution = tmp_path / "execution.json"
    assert OPS.execute(
        execute_args(plan, execution, manifest=manifest, apply=True)
    ) == 2
    assert real.read_text() == "original"
    assert link.is_symlink()


def test_invalid_plan_id_is_rejected(tmp_path: Path):
    discovery = tmp_path / "discovery.json"
    request = tmp_path / "request.json"
    write_json(discovery, {"host": {}})
    write_json(
        request,
        {
            "plan_id": "../../escape",
            "actions": [{"type": "mkdir", "path": str(tmp_path / "x")}],
        },
    )
    with pytest.raises(ValueError, match="plan_id"):
        OPS.make_plan(plan_args(discovery, request, tmp_path / "plan.json"))
