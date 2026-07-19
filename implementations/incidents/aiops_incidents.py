#!/usr/bin/env python3
"""Manage deterministic AI-OPS incident lifecycle state."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from report_store import ReportStore  # noqa: E402

STATE_RELATIVE = Path(".aiops-incidents/state.json")
LOCK_RELATIVE = Path(".aiops-incidents/incidents.lock")
STATUS_RELATIVE = Path("incident-status.json")
AUDIT_RELATIVE = Path(".aiops-audit/events.jsonl")
MAX_AUDIT_BYTES = 5 * 1024 * 1024
STATUSES = {"active", "acknowledged", "silenced", "resolved"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def write_json_atomic(path: Path, payload: dict[str, Any], mode: int = 0o640) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def append_audit_event(root: Path, event: dict[str, Any]) -> None:
    path = root / AUDIT_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.seek(0, os.SEEK_END)
        if stream.tell() >= MAX_AUDIT_BYTES:
            stream.close()
            rotated = path.with_suffix(path.suffix + ".1")
            if rotated.exists():
                rotated.unlink()
            os.replace(path, rotated)
            with path.open("a", encoding="utf-8") as replacement:
                replacement.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
                replacement.flush()
                os.fsync(replacement.fileno())
        else:
            stream.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    path.chmod(0o640)


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": "1.0", "updated_at": None, "incidents": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("incidents"), dict):
        raise ValueError("incident state must contain an incidents object")
    for alert_id, incident in payload["incidents"].items():
        if not isinstance(alert_id, str) or not isinstance(incident, dict):
            raise ValueError("invalid incident state entry")
        if incident.get("status") not in STATUSES:
            raise ValueError(f"invalid incident status for {alert_id}")
    return payload


def incident_id(alert_id: str) -> str:
    return "inc-" + hashlib.sha256(alert_id.encode("utf-8")).hexdigest()[:16]


def audit_event(
    transition: str,
    incident: dict[str, Any],
    *,
    actor: str,
    note: str,
    previous_status: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "event_id": str(uuid.uuid4()),
        "event_type": "incident-transition",
        "occurred_at": now(),
        "transition": transition,
        "incident_id": incident["incident_id"],
        "alert_id": incident["alert_id"],
        "severity": incident.get("severity"),
        "previous_status": previous_status,
        "status": incident["status"],
        "actor": actor,
        "note": note,
        "success": True,
    }


def normalize_alert(alert: dict[str, Any]) -> dict[str, Any]:
    alert_id = str(alert.get("id") or "")
    if not alert_id:
        raise ValueError("alert id is required")
    return {
        "alert_id": alert_id,
        "alert_type": str(alert.get("type") or "unknown"),
        "severity": str(alert.get("severity") or "info"),
        "report": str(alert.get("report") or ""),
        "category": str(alert.get("category") or "other"),
        "message": str(alert.get("message") or ""),
    }


def sync_state(
    state: dict[str, Any],
    alerts: list[dict[str, Any]],
    *,
    actor: str = "system",
    timestamp: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    current = timestamp or now()
    current_dt = parse_timestamp(current)
    incidents = {key: dict(value) for key, value in state.get("incidents", {}).items()}
    events: list[dict[str, Any]] = []
    active_alerts: dict[str, dict[str, Any]] = {}

    for raw in alerts:
        alert = normalize_alert(raw)
        if alert["report"] == STATUS_RELATIVE.as_posix():
            continue
        active_alerts[alert["alert_id"]] = alert

    for alert_id, alert in active_alerts.items():
        incident = incidents.get(alert_id)
        if incident is None:
            incident = {
                "incident_id": incident_id(alert_id),
                **alert,
                "status": "active",
                "first_seen_at": current,
                "last_seen_at": current,
                "occurrence_count": 1,
                "acknowledged_at": None,
                "acknowledged_by": None,
                "acknowledge_note": None,
                "silenced_at": None,
                "silenced_until": None,
                "silenced_by": None,
                "silence_note": None,
                "resolved_at": None,
                "resolved_by": None,
                "resolution_note": None,
                "resolution_reason": None,
            }
            incidents[alert_id] = incident
            events.append(
                audit_event(
                    "opened", incident, actor=actor, note="alert became active", previous_status=None
                )
            )
            continue

        previous = str(incident["status"])
        incident.update(alert)
        incident["last_seen_at"] = current
        incident["occurrence_count"] = int(incident.get("occurrence_count", 0)) + 1

        if previous == "resolved":
            incident["status"] = "active"
            incident["resolved_at"] = None
            incident["resolved_by"] = None
            incident["resolution_note"] = None
            incident["resolution_reason"] = None
            events.append(
                audit_event(
                    "reopened",
                    incident,
                    actor=actor,
                    note="alert is active again",
                    previous_status=previous,
                )
            )
        elif previous == "silenced":
            until = incident.get("silenced_until")
            if not isinstance(until, str) or parse_timestamp(until) <= current_dt:
                incident["status"] = "active"
                incident["silenced_at"] = None
                incident["silenced_until"] = None
                incident["silenced_by"] = None
                incident["silence_note"] = None
                events.append(
                    audit_event(
                        "silence-expired",
                        incident,
                        actor=actor,
                        note="silence interval expired",
                        previous_status=previous,
                    )
                )

    for alert_id, incident in incidents.items():
        if alert_id in active_alerts or incident.get("status") == "resolved":
            continue
        previous = str(incident["status"])
        incident["status"] = "resolved"
        incident["resolved_at"] = current
        incident["resolved_by"] = actor
        incident["resolution_note"] = "underlying alert cleared"
        incident["resolution_reason"] = "condition-cleared"
        events.append(
            audit_event(
                "auto-resolved",
                incident,
                actor=actor,
                note="underlying alert cleared",
                previous_status=previous,
            )
        )

    return {
        "schema_version": "1.0",
        "updated_at": current,
        "incidents": incidents,
    }, events


def summarize_state(state: dict[str, Any], *, mode: str, success: bool = True) -> dict[str, Any]:
    incidents = list(state.get("incidents", {}).values())
    counts = {status: 0 for status in sorted(STATUSES)}
    for incident in incidents:
        status = str(incident.get("status", "active"))
        counts[status] = counts.get(status, 0) + 1
    ordered = sorted(
        incidents,
        key=lambda item: (
            1 if item.get("status") == "resolved" else 0,
            {"critical": 0, "warning": 1, "info": 2}.get(str(item.get("severity")), 9),
            str(item.get("last_seen_at") or ""),
        ),
    )
    return {
        "schema_version": "1.0",
        "generated_at": now(),
        "mode": mode,
        "success": success,
        "summary": {
            "total": len(incidents),
            "open": counts.get("active", 0)
            + counts.get("acknowledged", 0)
            + counts.get("silenced", 0),
            **counts,
        },
        "incidents": ordered,
    }


def transition(
    state: dict[str, Any],
    alert_id: str,
    action: str,
    *,
    actor: str,
    note: str,
    silence_until: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    incidents = {key: dict(value) for key, value in state.get("incidents", {}).items()}
    incident = incidents.get(alert_id)
    if incident is None:
        raise KeyError(f"unknown alert id: {alert_id}")
    previous = str(incident.get("status"))
    current = now()

    if action == "acknowledge":
        if previous == "resolved":
            raise ValueError("resolved incident cannot be acknowledged")
        incident["status"] = "acknowledged"
        incident["acknowledged_at"] = current
        incident["acknowledged_by"] = actor
        incident["acknowledge_note"] = note
    elif action == "silence":
        if previous == "resolved":
            raise ValueError("resolved incident cannot be silenced")
        if not silence_until or parse_timestamp(silence_until) <= datetime.now(timezone.utc):
            raise ValueError("silence end must be in the future")
        incident["status"] = "silenced"
        incident["silenced_at"] = current
        incident["silenced_until"] = silence_until
        incident["silenced_by"] = actor
        incident["silence_note"] = note
    elif action == "unsilence":
        if previous != "silenced":
            raise ValueError("incident is not silenced")
        incident["status"] = "active"
        incident["silenced_at"] = None
        incident["silenced_until"] = None
        incident["silenced_by"] = None
        incident["silence_note"] = None
    elif action == "resolve":
        if previous == "resolved":
            raise ValueError("incident is already resolved")
        incident["status"] = "resolved"
        incident["resolved_at"] = current
        incident["resolved_by"] = actor
        incident["resolution_note"] = note
        incident["resolution_reason"] = "manual"
    else:
        raise ValueError(f"unsupported transition: {action}")

    incidents[alert_id] = incident
    updated = {"schema_version": "1.0", "updated_at": current, "incidents": incidents}
    event = audit_event(
        action,
        incident,
        actor=actor,
        note=note,
        previous_status=previous,
    )
    return updated, event


def resolve_path(root: Path, value: str | None, default: Path) -> Path:
    candidate = Path(value).expanduser() if value else default
    return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()


def write_result(
    root: Path,
    state_path: Path,
    status_path: Path,
    state: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    apply: bool,
) -> dict[str, Any]:
    report = summarize_state(state, mode="apply" if apply else "dry-run")
    write_json_atomic(status_path, report)
    if apply:
        write_json_atomic(state_path, state, mode=0o600)
        for event in events:
            append_audit_event(root, event)
    return report


def command_sync(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    state_path = resolve_path(root, args.state, STATE_RELATIVE)
    status_path = resolve_path(root, args.output, STATUS_RELATIVE)
    state = load_state(state_path)
    alerts = ReportStore(root).alerts()
    updated, events = sync_state(state, alerts, actor=args.actor)
    report = write_result(root, state_path, status_path, updated, events, apply=args.apply)
    print(status_path)
    return 0 if report["success"] else 2


def command_transition(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    state_path = resolve_path(root, args.state, STATE_RELATIVE)
    status_path = resolve_path(root, args.output, STATUS_RELATIVE)
    state = load_state(state_path)
    silence_until: str | None = None
    if args.command == "silence":
        if args.until:
            silence_until = parse_timestamp(args.until).isoformat()
        else:
            silence_until = (
                datetime.now(timezone.utc) + timedelta(minutes=args.minutes)
            ).isoformat()
    updated, event = transition(
        state,
        args.alert_id,
        args.command,
        actor=args.actor,
        note=args.note,
        silence_until=silence_until,
    )
    write_result(root, state_path, status_path, updated, [event], apply=args.apply)
    print(status_path)
    return 0


def command_list(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    state_path = resolve_path(root, args.state, STATE_RELATIVE)
    state = load_state(state_path)
    print(json.dumps(summarize_state(state, mode="read-only"), indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(PROJECT_ROOT))
    parser.add_argument("--state", default=STATE_RELATIVE.as_posix())
    parser.add_argument("--output", default=STATUS_RELATIVE.as_posix())
    parser.add_argument("--lock-file", default=LOCK_RELATIVE.as_posix())
    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync", help="Synchronize current deterministic alerts.")
    sync.add_argument("--actor", default="system")
    sync.add_argument("--apply", action="store_true")
    sync.set_defaults(handler=command_sync)

    listing = sub.add_parser("list", help="Print current incident state.")
    listing.set_defaults(handler=command_list)

    for name in ("acknowledge", "unsilence", "resolve"):
        item = sub.add_parser(name)
        item.add_argument("alert_id")
        item.add_argument("--actor", required=True)
        item.add_argument("--note", required=True)
        item.add_argument("--apply", action="store_true")
        item.set_defaults(handler=command_transition)

    silence = sub.add_parser("silence")
    silence.add_argument("alert_id")
    silence.add_argument("--actor", required=True)
    silence.add_argument("--note", required=True)
    group = silence.add_mutually_exclusive_group(required=True)
    group.add_argument("--until")
    group.add_argument("--minutes", type=int)
    silence.add_argument("--apply", action="store_true")
    silence.set_defaults(handler=command_transition)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"root directory does not exist: {root}")
    if getattr(args, "minutes", None) is not None and args.minutes < 1:
        parser.error("--minutes must be at least 1")
    lock_path = resolve_path(root, args.lock_file, LOCK_RELATIVE)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock_path.open("a+", encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            return int(args.handler(args))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Incident command failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
