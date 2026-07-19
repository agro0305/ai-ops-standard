from __future__ import annotations

import importlib.util
import json
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "implementations" / "incidents" / "aiops_incidents.py"
SPEC = importlib.util.spec_from_file_location("aiops_incidents", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def alert(alert_id: str = "refresh-failed:refresh-status.json") -> dict:
    return {
        "id": alert_id,
        "type": "refresh-failed",
        "severity": "critical",
        "report": "refresh-status.json",
        "category": "refresh",
        "message": "Refresh failed.",
    }


def empty_state() -> dict:
    return {"schema_version": "1.0", "updated_at": None, "incidents": {}}


def test_incident_opens_resolves_and_reopens_without_counting_every_sync():
    first_time = "2026-07-19T01:00:00+00:00"
    state, events = MODULE.sync_state(empty_state(), [alert()], timestamp=first_time)
    incident = state["incidents"][alert()["id"]]
    assert incident["status"] == "active"
    assert incident["occurrence_count"] == 1
    assert [event["transition"] for event in events] == ["opened"]

    state, events = MODULE.sync_state(
        state, [alert()], timestamp="2026-07-19T01:05:00+00:00"
    )
    assert state["incidents"][alert()["id"]]["occurrence_count"] == 1
    assert events == []

    state, events = MODULE.sync_state(
        state, [], timestamp="2026-07-19T01:10:00+00:00"
    )
    assert state["incidents"][alert()["id"]]["status"] == "resolved"
    assert events[0]["transition"] == "auto-resolved"

    state, events = MODULE.sync_state(
        state, [alert()], timestamp="2026-07-19T01:15:00+00:00"
    )
    incident = state["incidents"][alert()["id"]]
    assert incident["status"] == "active"
    assert incident["occurrence_count"] == 2
    assert events[0]["transition"] == "reopened"


def test_acknowledge_silence_and_unsilence_restore_acknowledged_state():
    state, _events = MODULE.sync_state(empty_state(), [alert()])
    state, event = MODULE.transition(
        state,
        alert()["id"],
        "acknowledge",
        actor="operator",
        note="Investigating",
    )
    assert state["incidents"][alert()["id"]]["status"] == "acknowledged"
    assert event["actor"] == "operator"

    until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    state, _event = MODULE.transition(
        state,
        alert()["id"],
        "silence",
        actor="operator",
        note="Maintenance",
        silence_until=until,
    )
    assert state["incidents"][alert()["id"]]["status"] == "silenced"
    assert state["incidents"][alert()["id"]]["pre_silence_status"] == "acknowledged"

    state, _event = MODULE.transition(
        state,
        alert()["id"],
        "unsilence",
        actor="operator",
        note="Maintenance complete",
    )
    incident = state["incidents"][alert()["id"]]
    assert incident["status"] == "acknowledged"
    assert incident["silenced_until"] is None


def test_expired_silence_is_removed_during_sync():
    state, _events = MODULE.sync_state(
        empty_state(), [alert()], timestamp="2026-07-19T01:00:00+00:00"
    )
    incident = state["incidents"][alert()["id"]]
    incident["status"] = "silenced"
    incident["pre_silence_status"] = "active"
    incident["silenced_until"] = "2026-07-19T01:02:00+00:00"

    state, events = MODULE.sync_state(
        state, [alert()], timestamp="2026-07-19T01:05:00+00:00"
    )
    assert state["incidents"][alert()["id"]]["status"] == "active"
    assert events[0]["transition"] == "silence-expired"


def test_dry_run_does_not_write_state_status_or_audit(tmp_path, capsys):
    (tmp_path / "compliance-result.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "summary": {"passed": 1, "failed": 1},
                "results": [],
            }
        ),
        encoding="utf-8",
    )
    args = Namespace(
        root=str(tmp_path),
        state=MODULE.STATE_RELATIVE.as_posix(),
        output=MODULE.STATUS_RELATIVE.as_posix(),
        actor="test",
        apply=False,
    )
    assert MODULE.command_sync(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "dry-run"
    assert payload["summary"]["open"] == 1
    assert not (tmp_path / MODULE.STATE_RELATIVE).exists()
    assert not (tmp_path / MODULE.STATUS_RELATIVE).exists()
    assert not (tmp_path / MODULE.AUDIT_RELATIVE).exists()


def test_apply_writes_private_state_public_status_and_audit(tmp_path):
    (tmp_path / "compliance-result.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "summary": {"passed": 1, "failed": 1},
                "results": [],
            }
        ),
        encoding="utf-8",
    )
    args = Namespace(
        root=str(tmp_path),
        state=MODULE.STATE_RELATIVE.as_posix(),
        output=MODULE.STATUS_RELATIVE.as_posix(),
        actor="test",
        apply=True,
    )
    assert MODULE.command_sync(args) == 0
    assert (tmp_path / MODULE.STATE_RELATIVE).is_file()
    assert (tmp_path / MODULE.STATUS_RELATIVE).is_file()
    assert (tmp_path / MODULE.AUDIT_RELATIVE).is_file()
    assert (tmp_path / MODULE.STATE_RELATIVE).suffix == ".private"


def test_manual_resolution_reopens_when_alert_persists():
    state, _events = MODULE.sync_state(empty_state(), [alert()])
    state, _event = MODULE.transition(
        state,
        alert()["id"],
        "resolve",
        actor="operator",
        note="Attempted remediation",
    )
    assert state["incidents"][alert()["id"]]["status"] == "resolved"
    state, events = MODULE.sync_state(state, [alert()])
    assert state["incidents"][alert()["id"]]["status"] == "active"
    assert events[0]["transition"] == "reopened"
