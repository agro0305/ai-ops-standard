#!/usr/bin/env python3
"""Check AI-OPS runtime reports, systemd units and dashboard endpoints."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_LIMITS = {
    "discovery-report.json": 45 * 60,
    "ai-capability-registry.json": 45 * 60,
    "compliance-result.json": 45 * 60,
    "refresh-status.json": 45 * 60,
    "incident-status.json": 20 * 60,
    "notification-status.json": 20 * 60,
}
SERVICES = {
    "aiops-dashboard.service": "active",
    "aiops-report-refresh.timer": "active",
    "aiops-incidents.timer": "active",
    "aiops-notifications.timer": "active",
    "aiops-retention.timer": "active",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
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
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def result(name: str, status: str, message: str, **details: Any) -> dict[str, Any]:
    return {"name": name, "status": status, "message": message, **details}


def check_json_report(
    root: Path, name: str, maximum_age: int, *, required: bool
) -> dict[str, Any]:
    path = root / name
    if not path.is_file():
        return result(
            f"report:{name}",
            "fail" if required else "warn",
            "report is missing",
            path=str(path),
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return result(
            f"report:{name}", "fail", "report is not valid JSON", error=str(exc)
        )
    age = max(0, int(time.time() - path.stat().st_mtime))
    if age > maximum_age:
        return result(
            f"report:{name}",
            "fail" if required else "warn",
            "report is stale",
            age_seconds=age,
            maximum_age_seconds=maximum_age,
        )
    if isinstance(payload, dict) and payload.get("success") is False:
        return result(
            f"report:{name}",
            "fail",
            "report records an unsuccessful run",
            age_seconds=age,
        )
    return result(
        f"report:{name}", "pass", "report is valid and fresh", age_seconds=age
    )


def systemctl_state(unit: str) -> tuple[str | None, str | None]:
    try:
        completed = subprocess.run(
            ["systemctl", "is-active", unit],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    state = (completed.stdout or completed.stderr).strip() or "unknown"
    return state, None


def check_unit(unit: str, expected: str, *, required: bool) -> dict[str, Any]:
    state, error = systemctl_state(unit)
    if error:
        return result(
            f"systemd:{unit}",
            "fail" if required else "warn",
            "systemctl is unavailable",
            error=error,
        )
    if state != expected:
        return result(
            f"systemd:{unit}",
            "fail" if required else "warn",
            f"unit state is {state}, expected {expected}",
            state=state,
        )
    return result(f"systemd:{unit}", "pass", f"unit is {state}", state=state)


def check_http(url: str, *, required: bool) -> dict[str, Any]:
    try:
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "aiops-runtime-health/1.0"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            status = int(response.status)
            body = response.read(4096).decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return result(
            f"http:{url}",
            "fail" if required else "warn",
            "endpoint is unavailable",
            error=str(exc),
        )
    if not 200 <= status < 300:
        return result(
            f"http:{url}", "fail", f"unexpected HTTP status {status}", status=status
        )
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = None
    return result(
        f"http:{url}", "pass", "endpoint is available", status=status, payload=payload
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:8789")
    parser.add_argument("--require-services", action="store_true")
    parser.add_argument("--output", default="runtime-health.json")
    args = parser.parse_args()

    root = Path(args.project_root).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"project root does not exist: {root}")

    checks: list[dict[str, Any]] = []
    version_path = root / "VERSION"
    if version_path.is_file():
        checks.append(
            result(
                "version",
                "pass",
                "VERSION file is present",
                version=version_path.read_text(encoding="utf-8").strip(),
            )
        )
    else:
        checks.append(result("version", "fail", "VERSION file is missing"))

    for name, limit in REPORT_LIMITS.items():
        checks.append(
            check_json_report(root, name, limit, required=args.require_services)
        )

    audit_path = root / ".aiops-audit/events.jsonl"
    checks.append(
        result(
            "audit-log",
            "pass" if audit_path.is_file() else ("fail" if args.require_services else "warn"),
            "audit log is present" if audit_path.is_file() else "audit log is missing",
            path=str(audit_path),
        )
    )

    for unit, expected in SERVICES.items():
        checks.append(check_unit(unit, expected, required=args.require_services))

    base = args.dashboard_url.rstrip("/")
    checks.append(check_http(f"{base}/healthz", required=args.require_services))
    checks.append(check_http(f"{base}/readyz", required=args.require_services))

    counts = {"pass": 0, "warn": 0, "fail": 0}
    for check in checks:
        counts[check["status"]] = counts.get(check["status"], 0) + 1
    report = {
        "schema_version": "1.0",
        "generated_at": now(),
        "project_root": str(root),
        "dashboard_url": base,
        "require_services": args.require_services,
        "success": counts["fail"] == 0,
        "summary": counts,
        "checks": checks,
    }
    output = Path(args.output).expanduser().resolve()
    write_json_atomic(output, report)
    print(output)
    return 0 if report["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
