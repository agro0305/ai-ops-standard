from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ACCEPTANCE = load_module("aiops_acceptance_tests", ROOT / "scripts" / "acceptance.py")
HEALTH = load_module("aiops_runtime_health_tests", ROOT / "scripts" / "runtime_health.py")


def test_acceptance_write_json_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "result.json"
    ACCEPTANCE.write_json(path, {"success": True})
    assert json.loads(path.read_text(encoding="utf-8")) == {"success": True}


def test_acceptance_run_step_captures_success_and_failure(tmp_path):
    success = ACCEPTANCE.run_step(
        "success", ["python3", "-c", "print('ok')"], cwd=tmp_path
    )
    failure = ACCEPTANCE.run_step(
        "failure", ["python3", "-c", "raise SystemExit(7)"], cwd=tmp_path
    )
    assert success["accepted"] is True
    assert "ok" in success["stdout"]
    assert failure["accepted"] is False
    assert failure["returncode"] == 7


def test_runtime_health_valid_fresh_report_passes(tmp_path):
    path = tmp_path / "refresh-status.json"
    path.write_text(json.dumps({"success": True}), encoding="utf-8")
    check = HEALTH.check_json_report(
        tmp_path, "refresh-status.json", 60, required=True
    )
    assert check["status"] == "pass"


def test_runtime_health_stale_and_failed_reports_fail(tmp_path):
    stale = tmp_path / "discovery-report.json"
    stale.write_text("{}", encoding="utf-8")
    old = time.time() - 120
    os.utime(stale, (old, old))
    stale_check = HEALTH.check_json_report(
        tmp_path, "discovery-report.json", 1, required=True
    )
    assert stale_check["status"] == "fail"
    assert stale_check["message"] == "report is stale"

    failed = tmp_path / "notification-status.json"
    failed.write_text(json.dumps({"success": False}), encoding="utf-8")
    failed_check = HEALTH.check_json_report(
        tmp_path, "notification-status.json", 60, required=True
    )
    assert failed_check["status"] == "fail"
    assert "unsuccessful" in failed_check["message"]


def test_runtime_health_missing_optional_report_warns(tmp_path):
    check = HEALTH.check_json_report(
        tmp_path, "incident-status.json", 60, required=False
    )
    assert check["status"] == "warn"


def test_runtime_health_unit_check_uses_expected_state(monkeypatch):
    monkeypatch.setattr(HEALTH, "systemctl_state", lambda _unit: ("active", None))
    assert HEALTH.check_unit("example.timer", "active", required=True)["status"] == "pass"

    monkeypatch.setattr(HEALTH, "systemctl_state", lambda _unit: ("inactive", None))
    assert HEALTH.check_unit("example.timer", "active", required=True)["status"] == "fail"
