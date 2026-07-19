#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

from report_store import ReportStore

AUDIT_RELATIVE_PATH = Path(".aiops-audit/events.jsonl")
MAX_AUDIT_LINE_BYTES = 256 * 1024


def read_audit_events(root: str | Path, limit: int = 100) -> dict[str, Any]:
    """Read the newest valid audit events without loading the whole file."""
    if limit < 1 or limit > 1000:
        raise ValueError("audit limit must be between 1 and 1000")

    root_path = Path(root).expanduser().resolve()
    audit_path = root_path / AUDIT_RELATIVE_PATH
    if not audit_path.is_file() or audit_path.is_symlink():
        return {"events": [], "invalid_lines": 0, "source": str(AUDIT_RELATIVE_PATH)}

    lines: deque[bytes] = deque(maxlen=limit * 2)
    with audit_path.open("rb") as stream:
        for line in stream:
            if len(line) <= MAX_AUDIT_LINE_BYTES:
                lines.append(line)

    events: list[dict[str, Any]] = []
    invalid = 0
    for raw in reversed(lines):
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            invalid += 1
            continue
        if not isinstance(payload, dict):
            invalid += 1
            continue
        events.append(payload)
        if len(events) >= limit:
            break

    return {
        "events": events,
        "invalid_lines": invalid,
        "source": str(AUDIT_RELATIVE_PATH),
    }


def _metric(name: str, value: int | float, labels: dict[str, str] | None = None) -> str:
    suffix = ""
    if labels:
        encoded = ",".join(
            f'{key}="{str(item).replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"'
            for key, item in sorted(labels.items())
        )
        suffix = "{" + encoded + "}"
    return f"{name}{suffix} {value}"


def render_prometheus_metrics(store: ReportStore) -> str:
    reports = store.list_reports()
    alerts = store.alerts(reports)
    summary = store.summary()

    lines = [
        "# HELP aiops_reports_total Number of indexed AI-OPS JSON reports.",
        "# TYPE aiops_reports_total gauge",
        _metric("aiops_reports_total", int(summary.get("report_count", 0))),
        "# HELP aiops_reports_stale Number of stale automatically refreshed reports.",
        "# TYPE aiops_reports_stale gauge",
        _metric("aiops_reports_stale", int(summary.get("stale_reports", 0))),
        "# HELP aiops_reports_invalid Number of reports that could not be parsed.",
        "# TYPE aiops_reports_invalid gauge",
        _metric("aiops_reports_invalid", int(summary.get("invalid_reports", 0))),
        "# HELP aiops_compliance_requirements Compliance requirement result counts.",
        "# TYPE aiops_compliance_requirements gauge",
        _metric("aiops_compliance_requirements", int(summary.get("compliance", {}).get("passed", 0)), {"result": "passed"}),
        _metric("aiops_compliance_requirements", int(summary.get("compliance", {}).get("failed", 0)), {"result": "failed"}),
        "# HELP aiops_alerts_total Active dashboard alerts by severity.",
        "# TYPE aiops_alerts_total gauge",
    ]

    for severity in ("critical", "warning", "info"):
        lines.append(
            _metric(
                "aiops_alerts_total",
                sum(1 for item in alerts if item.get("severity") == severity),
                {"severity": severity},
            )
        )

    categories: dict[str, int] = {}
    for report in reports:
        category = str(report.get("category", "other"))
        categories[category] = categories.get(category, 0) + 1
    lines.extend(
        [
            "# HELP aiops_reports_by_category Number of reports by category.",
            "# TYPE aiops_reports_by_category gauge",
        ]
    )
    for category, count in sorted(categories.items()):
        lines.append(_metric("aiops_reports_by_category", count, {"category": category}))

    refresh_reports = [item for item in reports if item.get("category") == "refresh"]
    refresh_reports.sort(key=lambda item: int(item.get("age_seconds", 0)))
    latest = refresh_reports[0] if refresh_reports else None
    lines.extend(
        [
            "# HELP aiops_last_refresh_success Whether the newest refresh report succeeded.",
            "# TYPE aiops_last_refresh_success gauge",
            _metric(
                "aiops_last_refresh_success",
                1 if latest and latest.get("summary", {}).get("success") is True else 0,
            ),
            "# HELP aiops_last_refresh_age_seconds Age of the newest refresh report.",
            "# TYPE aiops_last_refresh_age_seconds gauge",
            _metric("aiops_last_refresh_age_seconds", int(latest.get("age_seconds", 0)) if latest else -1),
        ]
    )

    return "\n".join(lines) + "\n"
