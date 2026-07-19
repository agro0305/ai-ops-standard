from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "notify_alerts.py"
SPEC = importlib.util.spec_from_file_location("aiops_notify_alerts", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def critical_report(root: Path) -> None:
    write_json(
        root / "execution-report.json",
        {
            "plan_id": "plan-test",
            "started_at": "2026-07-19T00:00:00+00:00",
            "finished_at": "2026-07-19T00:00:01+00:00",
            "apply": True,
            "success": False,
            "results": [],
        },
    )


def config(path: Path, channels: list[dict] | None = None) -> None:
    write_json(
        path,
        {
            "schema_version": "1.0",
            "minimum_severity": "critical",
            "cooldown_seconds": 3600,
            "state_retention_seconds": 86400,
            "channels": channels if channels is not None else [{"type": "stdout", "enabled": True}],
        },
    )


def args(root: Path, config_path: Path, *, apply: bool) -> argparse.Namespace:
    return argparse.Namespace(
        root=str(root),
        config=str(config_path),
        state=".aiops-notifications/state.json",
        output="notification-status.json",
        lock_file=".aiops-notifications/dispatch.lock",
        apply=apply,
    )


def test_select_alerts_filters_severity_and_cooldown():
    alerts = [
        {"id": "warning", "severity": "warning", "report": "a.json", "message": "warning"},
        {"id": "critical", "severity": "critical", "report": "b.json", "message": "critical"},
    ]
    fingerprint = MODULE.alert_fingerprint(alerts[1])
    state = {"sent": {fingerprint: "2026-07-19T00:00:00+00:00"}}
    eligible, pending, suppressed = MODULE.select_alerts(
        alerts,
        state,
        minimum_severity="critical",
        cooldown_seconds=3600,
        current_time=MODULE.parse_time("2026-07-19T00:30:00+00:00"),
    )
    assert len(eligible) == 1
    assert pending == []
    assert len(suppressed) == 1
    assert suppressed[0]["cooldown_remaining_seconds"] == 1800


def test_dry_run_writes_status_without_notification_state(tmp_path):
    critical_report(tmp_path)
    config_path = tmp_path / "notifications.json"
    config(config_path)

    code, status = MODULE.run(args(tmp_path, config_path, apply=False))

    assert code == 0
    assert status["mode"] == "dry-run"
    assert status["pending_alerts"] == 1
    assert status["dispatched_alerts"] == 0
    assert not (tmp_path / ".aiops-notifications/state.json").exists()
    assert (tmp_path / "notification-status.json").exists()
    assert (tmp_path / ".aiops-audit/events.jsonl").exists()


def test_apply_updates_state_and_suppresses_duplicate(tmp_path, capsys):
    critical_report(tmp_path)
    config_path = tmp_path / "notifications.json"
    config(config_path)

    first_code, first = MODULE.run(args(tmp_path, config_path, apply=True))
    second_code, second = MODULE.run(args(tmp_path, config_path, apply=True))

    assert first_code == 0
    assert first["dispatched_alerts"] == 1
    assert second_code == 0
    assert second["pending_alerts"] == 0
    assert second["suppressed_alerts"] == 1
    state = json.loads(
        (tmp_path / ".aiops-notifications/state.json").read_text(encoding="utf-8")
    )
    assert len(state["sent"]) == 1
    assert "AI-OPS alerts" in capsys.readouterr().out


def test_failed_webhook_does_not_update_state(tmp_path, monkeypatch):
    critical_report(tmp_path)
    config_path = tmp_path / "notifications.json"
    config(
        config_path,
        [
            {
                "type": "webhook",
                "enabled": True,
                "url_env": "AIOPS_TEST_WEBHOOK_URL",
                "token_env": "AIOPS_TEST_WEBHOOK_TOKEN",
                "timeout_seconds": 1,
            }
        ],
    )
    monkeypatch.delenv("AIOPS_TEST_WEBHOOK_URL", raising=False)

    code, status = MODULE.run(args(tmp_path, config_path, apply=True))

    assert code == 2
    assert status["success"] is False
    assert status["channel_results"][0]["type"] == "webhook"
    assert not (tmp_path / ".aiops-notifications/state.json").exists()


def test_config_rejects_unknown_channel(tmp_path):
    path = tmp_path / "notifications.json"
    config(path, [{"type": "shell", "enabled": True}])
    try:
        MODULE.validate_config(json.loads(path.read_text(encoding="utf-8")))
    except ValueError as exc:
        assert "unsupported channel" in str(exc)
    else:
        raise AssertionError("unknown notification channels must be rejected")
