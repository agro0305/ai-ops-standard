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


REPORT_STORE = load_module("aiops_report_store_alerts", ROOT / "dashboard" / "report_store.py")
REFRESH = load_module("aiops_refresh_reports_audit", ROOT / "scripts" / "refresh_reports.py")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_refresh_report_is_classified_and_summarized(tmp_path):
    path = tmp_path / "refresh-status.json"
    write_json(
        path,
        {
            "success": True,
            "steps": [{"name": "discovery", "accepted": True}],
            "reports": ["discovery-report.json"],
            "project_root": "/srv/aiops",
            "generated_at": "2026-07-19T00:00:00+00:00",
            "duration_seconds": 3.2,
        },
    )
    report = REPORT_STORE.ReportStore(tmp_path).list_reports()[0]
    assert report["category"] == "refresh"
    assert report["summary"]["success"] is True
    assert report["summary"]["failed_steps"] == 0


def test_stale_and_failed_refresh_create_alerts(tmp_path):
    path = tmp_path / "refresh-status.json"
    write_json(
        path,
        {
            "success": False,
            "steps": [{"name": "discovery", "accepted": False}],
            "reports": [],
            "project_root": "/srv/aiops",
            "generated_at": "2026-07-19T00:00:00+00:00",
        },
    )
    old = time.time() - 120
    os.utime(path, (old, old))
    store = REPORT_STORE.ReportStore(tmp_path, freshness_seconds={"refresh": 1})
    alerts = store.alerts()
    assert {item["type"] for item in alerts} == {"stale-report", "refresh-failed"}
    assert alerts[0]["severity"] == "critical"
    summary = store.summary()
    assert summary["stale_reports"] == 1
    assert summary["alerts"]["critical"] == 1
    assert summary["alerts"]["warning"] == 1


def test_compliance_failure_creates_warning(tmp_path):
    write_json(
        tmp_path / "compliance-result.json",
        {
            "generated_at": "2026-07-19T00:00:00+00:00",
            "summary": {"passed": 3, "failed": 2},
            "results": [],
        },
    )
    store = REPORT_STORE.ReportStore(
        tmp_path, freshness_seconds={"compliance": 10**9}
    )
    alerts = store.alerts()
    assert len(alerts) == 1
    assert alerts[0]["type"] == "compliance-failed"
    assert alerts[0]["severity"] == "warning"


def test_invalid_json_creates_critical_alert(tmp_path):
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    alerts = REPORT_STORE.ReportStore(tmp_path).alerts()
    assert alerts[0]["type"] == "invalid-report"
    assert alerts[0]["severity"] == "critical"


def test_refresh_audit_is_jsonl_and_hidden_from_report_index(tmp_path):
    audit_path = tmp_path / ".aiops-audit" / "events.jsonl"
    status = {
        "generated_at": "2026-07-19T00:00:00+00:00",
        "success": True,
        "duration_seconds": 4.5,
        "project_root": "/srv/aiops",
        "output_dir": str(tmp_path),
        "reports": ["discovery-report.json"],
        "steps": [{"name": "discovery", "accepted": True}],
    }
    event = REFRESH.audit_from_status(status)
    REFRESH.append_audit_event(audit_path, event)
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    loaded = json.loads(lines[0])
    assert loaded["event_type"] == "report-refresh"
    assert loaded["success"] is True
    assert REPORT_STORE.ReportStore(tmp_path).list_reports() == []
