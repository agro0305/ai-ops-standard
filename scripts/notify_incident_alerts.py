#!/usr/bin/env python3
"""Run the existing notifier while respecting incident lifecycle state."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import notify_alerts as notifier  # noqa: E402

INCIDENT_STATE_RELATIVE = Path(".aiops-incidents/state.json.private")
BASE_REPORT_STORE = notifier.ReportStore


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def load_incident_state(root: Path) -> dict[str, Any] | None:
    path = root / INCIDENT_STATE_RELATIVE
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    incidents = payload.get("incidents") if isinstance(payload, dict) else None
    return incidents if isinstance(incidents, dict) else None


def filter_alerts_by_incidents(
    alerts: list[dict[str, Any]],
    incidents: dict[str, Any] | None,
    *,
    current_time: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if incidents is None:
        return list(alerts), []
    moment = current_time or datetime.now(timezone.utc)
    deliver: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []

    for alert in alerts:
        alert_id = str(alert.get("id") or "")
        incident = incidents.get(alert_id)
        if not isinstance(incident, dict):
            deliver.append(alert)
            continue
        status = str(incident.get("status") or "active")
        if status == "active":
            deliver.append(alert)
            continue
        if status == "silenced":
            until = incident.get("silenced_until")
            try:
                expired = not isinstance(until, str) or parse_timestamp(until) <= moment
            except ValueError:
                expired = True
            if expired:
                deliver.append(alert)
                continue
        suppressed.append({**alert, "incident_status": status})
    return deliver, suppressed


class IncidentAwareReportStore(BASE_REPORT_STORE):
    def alerts(
        self, reports: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        raw = super().alerts(reports)
        filtered, _suppressed = filter_alerts_by_incidents(
            raw, load_incident_state(self.root)
        )
        return filtered


def main() -> int:
    notifier.ReportStore = IncidentAwareReportStore
    return int(notifier.main())


if __name__ == "__main__":
    raise SystemExit(main())
