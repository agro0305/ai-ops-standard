import importlib.util
import json
from argparse import Namespace
from pathlib import Path

MODULE_PATH = Path(__file__).parents[2] / "implementations" / "operations" / "aiops_operations.py"
spec = importlib.util.spec_from_file_location("aiops_operations", MODULE_PATH)
ops = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(ops)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_risk_classification():
    assert ops.classify_risk([{"type": "write_file", "path": "/tmp/x"}]) == "low"
    assert ops.classify_risk([{"type": "write_file", "path": "/etc/x"}]) == "high"
    assert ops.classify_risk([{"type": "delete", "path": "/tmp/x"}]) == "high"
    assert ops.classify_risk([{"type": "write_file", "path": "/tmp/x", "safety_critical": True}]) == "critical"


def test_plan_backup_execute_verify_and_rollback(tmp_path: Path):
    target = tmp_path / "target.txt"
    target.write_text("before\n", encoding="utf-8")
    discovery = tmp_path / "discovery.json"
    request = tmp_path / "request.json"
    plan_path = tmp_path / "plan.json"
    write_json(discovery, {"host": {"hostname": "test"}})
    write_json(request, {
        "plan_id": "test-plan",
        "intent": "test operation",
        "actions": [{"type": "write_file", "path": str(target), "content": "after\n"}],
        "verification": [{"type": "file_contains", "path": str(target), "text": "after"}],
    })

    assert ops.make_plan(Namespace(discovery=str(discovery), request=str(request), output=str(plan_path))) == 0
    plan = json.loads(plan_path.read_text())
    assert plan["risk"]["level"] == "low"
    assert plan["backup"]["required"] is True

    backup_root = tmp_path / "backups"
    assert ops.make_backup(Namespace(plan=str(plan_path), backup_root=str(backup_root))) == 0
    manifest = backup_root / "test-plan" / "backup-manifest.json"
    assert manifest.exists()

    execution = tmp_path / "execution.json"
    assert ops.execute(Namespace(plan=str(plan_path), output=str(execution), apply=True, approved=False, continue_on_error=False)) == 0
    assert target.read_text() == "after\n"

    verification = tmp_path / "verification.json"
    assert ops.verify(Namespace(plan=str(plan_path), output=str(verification))) == 0
    assert json.loads(verification.read_text())["passed"] is True

    rollback = tmp_path / "rollback.json"
    assert ops.rollback(Namespace(manifest=str(manifest), output=str(rollback))) == 0
    assert target.read_text() == "before\n"


def test_dry_run_does_not_change_target(tmp_path: Path):
    target = tmp_path / "target.txt"
    plan = tmp_path / "plan.json"
    write_json(plan, {
        "plan_id": "dry-run",
        "risk": {"approval_required": False},
        "actions": [{"type": "write_file", "path": str(target), "content": "changed"}],
    })
    output = tmp_path / "execution.json"
    assert ops.execute(Namespace(plan=str(plan), output=str(output), apply=False, approved=False, continue_on_error=False)) == 0
    assert not target.exists()


def test_high_risk_requires_approval(tmp_path: Path):
    plan = tmp_path / "plan.json"
    write_json(plan, {
        "plan_id": "high-risk",
        "risk": {"approval_required": True},
        "actions": [],
    })
    try:
        ops.execute(Namespace(plan=str(plan), output=str(tmp_path / "out.json"), apply=True, approved=False, continue_on_error=False))
    except PermissionError:
        pass
    else:
        raise AssertionError("approval was not enforced")
