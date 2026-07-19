from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "notify_incident_alerts.py"
SPEC = importlib.util.spec_from_file_location("notify_incident_alerts", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def alert(alert_id: str, severity: str = "critical") -> dict:
    return {
        "id": alert_id,
        "type": "test",
        "severity": severity,
        "report": "test.json",
        "category": "test",
        "message": "Test alert",
    }


def test_missing_incident_state_does_not_suppress_alerts():
    alerts = [alert("a"), alert("b")]
    delivered, suppressed = MODULE.filter_alerts_by_incidents(alerts, None)
    assert delivered == alerts
    assert suppressed == []


def test_acknowledged_and_resolved_incidents_are_suppressed():
    alerts = [alert("active"), alert("ack"), alert("resolved")]
    incidents = {
        "active": {"status": "active"},
        "ack": {"status": "acknowledged"},
        "resolved": {"status": "resolved"},
    }
    delivered, suppressed = MODULE.filter_alerts_by_incidents(alerts, incidents)
    assert [item["id"] for item in delivered] == ["active"]
    assert {item["id"] for item in suppressed} == {"ack", "resolved"}


def test_active_silence_suppresses_but_expired_silence_delivers():
    moment = datetime.now(timezone.utc)
    alerts = [alert("active-silence"), alert("expired-silence")]
    incidents = {
        "active-silence": {
            "status": "silenced",
            "silenced_until": (moment + timedelta(minutes=30)).isoformat(),
        },
        "expired-silence": {
            "status": "silenced",
            "silenced_until": (moment - timedelta(minutes=1)).isoformat(),
        },
    }
    delivered, suppressed = MODULE.filter_alerts_by_incidents(
        alerts, incidents, current_time=moment
    )
    assert [item["id"] for item in delivered] == ["expired-silence"]
    assert [item["id"] for item in suppressed] == ["active-silence"]


def test_invalid_silence_timestamp_fails_open():
    alerts = [alert("bad-silence")]
    incidents = {
        "bad-silence": {"status": "silenced", "silenced_until": "invalid"}
    }
    delivered, suppressed = MODULE.filter_alerts_by_incidents(alerts, incidents)
    assert delivered == alerts
    assert suppressed == []
