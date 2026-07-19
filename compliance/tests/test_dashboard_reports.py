from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "dashboard" / "report_store.py"
SPEC = importlib.util.spec_from_file_location("aiops_report_store", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_report_store_classifies_and_summarizes_reports(tmp_path):
    write_json(
        tmp_path / "discovery-report.json",
        {
            "report_id": "r1",
            "generated_at": "2026-07-19T00:00:00+00:00",
            "collectors": {"system": {}, "network": {}},
            "errors": [],
            "effective_user": {"name": "tester"},
        },
    )
    write_json(
        tmp_path / "compliance-result.json",
        {
            "summary": {"passed": 3, "failed": 1},
            "results": [],
            "generated_at": "2026-07-19T00:00:00+00:00",
        },
    )
    store = MODULE.ReportStore(tmp_path)
    reports = store.list_reports()
    assert [item["category"] for item in reports] == ["compliance", "discovery"]
    summary = store.summary()
    assert summary["report_count"] == 2
    assert summary["compliance"] == {"passed": 3, "failed": 1}


def test_report_store_reads_nested_backup_manifest(tmp_path):
    write_json(
        tmp_path / ".aiops-backups" / "plan-1" / "backup-manifest.json",
        {
            "plan_id": "plan-1",
            "backup_root": "/tmp/backup",
            "entries": [{"source": "/tmp/example", "existed": False}],
            "complete": True,
        },
    )
    store = MODULE.ReportStore(tmp_path)
    reports = store.list_reports()
    assert reports[0]["name"] == ".aiops-backups/plan-1/backup-manifest.json"
    assert reports[0]["category"] == "backup"
    detail = store.get_report(reports[0]["name"])
    assert detail["data"]["plan_id"] == "plan-1"


def test_report_store_rejects_path_traversal(tmp_path):
    store = MODULE.ReportStore(tmp_path)
    for name in ("../secret.json", "/etc/passwd", r"..\secret.json"):
        try:
            store.resolve_name(name)
        except (ValueError, FileNotFoundError):
            pass
        else:
            raise AssertionError(f"path traversal accepted: {name}")


def test_report_store_reports_invalid_json_without_crashing(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{broken", encoding="utf-8")
    report = MODULE.ReportStore(tmp_path).list_reports()[0]
    assert report["name"] == "broken.json"
    assert "error" in report


def test_report_store_skips_symlinked_reports(tmp_path):
    outside = tmp_path.parent / "outside-report.json"
    outside.write_text("{}", encoding="utf-8")
    link = tmp_path / "linked.json"
    try:
        link.symlink_to(outside)
    except OSError:
        return
    assert MODULE.ReportStore(tmp_path).list_reports() == []
