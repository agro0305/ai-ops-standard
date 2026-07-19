from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STORE_PATH = ROOT / "dashboard" / "report_store.py"
SPEC = importlib.util.spec_from_file_location("incident_dashboard_store", STORE_PATH)
assert SPEC and SPEC.loader
STORE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STORE)


def test_private_incident_state_is_not_indexed_but_status_is_visible(tmp_path):
    private = tmp_path / ".aiops-incidents" / "state.json.private"
    private.parent.mkdir(parents=True)
    private.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "updated_at": None,
                "incidents": {"secret-alert": {"status": "active"}},
            }
        ),
        encoding="utf-8",
    )
    public = tmp_path / "incident-status.json"
    public.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": "2026-07-19T00:00:00+00:00",
                "mode": "apply",
                "success": True,
                "summary": {
                    "total": 1,
                    "open": 1,
                    "active": 1,
                    "acknowledged": 0,
                    "silenced": 0,
                    "resolved": 0,
                },
                "incidents": [],
            }
        ),
        encoding="utf-8",
    )

    reports = STORE.ReportStore(tmp_path).list_reports()
    assert [item["name"] for item in reports] == ["incident-status.json"]
    assert "state.json.private" not in json.dumps(reports)


def test_dashboard_contains_read_only_incident_panel():
    index = (ROOT / "dashboard" / "static" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "dashboard" / "static" / "app.js").read_text(encoding="utf-8")
    server = (ROOT / "dashboard" / "server.py").read_text(encoding="utf-8")

    assert 'id="incident-list"' in index
    assert "/api/reports/incident-status.json" in app
    assert "<form" not in index.lower()
    assert 'method: "post"' not in app.lower()
    assert "method: 'post'" not in app.lower()
    assert "/api/incidents/" not in app
    assert "def do_POST" not in server
