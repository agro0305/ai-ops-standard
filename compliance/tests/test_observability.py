from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


DASHBOARD_DIR = Path(__file__).resolve().parents[2] / "dashboard"
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

SPEC = importlib.util.spec_from_file_location(
    "aiops_observability", DASHBOARD_DIR / "observability.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

from report_store import ReportStore  # noqa: E402


def test_audit_reader_returns_newest_valid_events(tmp_path):
    audit = tmp_path / ".aiops-audit"
    audit.mkdir()
    path = audit / "events.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"event_id": "one", "occurred_at": "2026-01-01T00:00:00Z"}),
                "not-json",
                json.dumps({"event_id": "two", "occurred_at": "2026-01-02T00:00:00Z"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = MODULE.read_audit_events(tmp_path, limit=10)
    assert [item["event_id"] for item in result["events"]] == ["two", "one"]
    assert result["invalid_lines"] == 1


def test_audit_reader_validates_limit(tmp_path):
    try:
        MODULE.read_audit_events(tmp_path, limit=0)
    except ValueError:
        pass
    else:
        raise AssertionError("zero audit limit must fail")


def test_prometheus_metrics_expose_report_alert_and_refresh_state(tmp_path):
    (tmp_path / "refresh-status.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": "2026-07-19T00:00:00+00:00",
                "success": True,
                "duration_seconds": 1.2,
                "project_root": str(tmp_path),
                "output_dir": str(tmp_path),
                "reports": ["discovery-report.json"],
                "steps": [],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "compliance-result.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "generated_at": "2026-07-19T00:00:00+00:00",
                "summary": {"passed": 3, "failed": 1},
                "results": [],
            }
        ),
        encoding="utf-8",
    )

    metrics = MODULE.render_prometheus_metrics(
        ReportStore(tmp_path, freshness_seconds={"refresh": 10**9, "compliance": 10**9})
    )
    assert "aiops_reports_total 2" in metrics
    assert 'aiops_compliance_requirements{result="passed"} 3' in metrics
    assert 'aiops_compliance_requirements{result="failed"} 1' in metrics
    assert 'aiops_alerts_total{severity="warning"} 1' in metrics
    assert "aiops_last_refresh_success 1" in metrics
