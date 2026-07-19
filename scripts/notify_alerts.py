#!/usr/bin/env python3
"""Dispatch deterministic AI-OPS alerts with cooldown and deduplication."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from report_store import ReportStore  # noqa: E402

SEVERITY = {"info": 0, "warning": 1, "critical": 2}
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_time(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


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


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": "1.0", "updated_at": None, "sent": {}}
    state = load_json(path)
    sent = state.get("sent", {})
    if not isinstance(sent, dict):
        raise ValueError("notification state.sent must be an object")
    return {
        "schema_version": "1.0",
        "updated_at": state.get("updated_at"),
        "sent": sent,
    }


def alert_fingerprint(alert: dict[str, Any]) -> str:
    stable = {
        "id": alert.get("id"),
        "severity": alert.get("severity"),
        "report": alert.get("report"),
        "message": alert.get("message"),
    }
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    minimum = str(config.get("minimum_severity", "critical"))
    if minimum not in SEVERITY:
        raise ValueError("minimum_severity must be info, warning or critical")
    cooldown = int(config.get("cooldown_seconds", 3600))
    if cooldown < 0:
        raise ValueError("cooldown_seconds must be zero or greater")
    retention = int(config.get("state_retention_seconds", 30 * 24 * 3600))
    if retention < cooldown:
        raise ValueError("state_retention_seconds must be at least cooldown_seconds")

    channels = config.get("channels", [])
    if not isinstance(channels, list):
        raise ValueError("channels must be an array")
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(channels):
        if not isinstance(raw, dict):
            raise ValueError(f"channels[{index}] must be an object")
        channel_type = str(raw.get("type", ""))
        if channel_type not in {"stdout", "webhook"}:
            raise ValueError(f"unsupported channel type: {channel_type}")
        enabled = bool(raw.get("enabled", True))
        item = {"type": channel_type, "enabled": enabled}
        if channel_type == "webhook":
            url_env = str(raw.get("url_env", "AIOPS_NOTIFICATION_WEBHOOK_URL"))
            token_env = str(raw.get("token_env", "AIOPS_NOTIFICATION_TOKEN"))
            if not ENV_NAME.fullmatch(url_env) or not ENV_NAME.fullmatch(token_env):
                raise ValueError("webhook environment variable names are invalid")
            timeout = int(raw.get("timeout_seconds", 10))
            if timeout < 1 or timeout > 60:
                raise ValueError("webhook timeout_seconds must be between 1 and 60")
            item.update(
                {
                    "url_env": url_env,
                    "token_env": token_env,
                    "timeout_seconds": timeout,
                    "allow_http": bool(raw.get("allow_http", False)),
                }
            )
        normalized.append(item)

    return {
        "schema_version": "1.0",
        "minimum_severity": minimum,
        "cooldown_seconds": cooldown,
        "state_retention_seconds": retention,
        "channels": normalized,
    }


def select_alerts(
    alerts: list[dict[str, Any]],
    state: dict[str, Any],
    *,
    minimum_severity: str,
    cooldown_seconds: int,
    current_time: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    timestamp = time.time() if current_time is None else current_time
    eligible: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    sent = state.get("sent", {})
    minimum_value = SEVERITY[minimum_severity]

    for alert in alerts:
        severity = str(alert.get("severity", "info"))
        if severity not in SEVERITY or SEVERITY[severity] < minimum_value:
            continue
        item = dict(alert)
        fingerprint = alert_fingerprint(item)
        item["fingerprint"] = fingerprint
        eligible.append(item)
        previous = sent.get(fingerprint)
        if not isinstance(previous, str):
            pending.append(item)
            continue
        try:
            elapsed = timestamp - parse_time(previous)
        except (ValueError, TypeError):
            pending.append(item)
            continue
        if elapsed >= cooldown_seconds:
            pending.append(item)
        else:
            item["cooldown_remaining_seconds"] = max(0, int(cooldown_seconds - elapsed))
            suppressed.append(item)
    return eligible, pending, suppressed


def notification_payload(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    host = socket.gethostname()
    return {
        "schema_version": "1.0",
        "generated_at": now(),
        "source": "ai-ops-standard",
        "host": host,
        "alert_count": len(alerts),
        "alerts": [
            {
                "id": item.get("id"),
                "severity": item.get("severity"),
                "type": item.get("type"),
                "report": item.get("report"),
                "category": item.get("category"),
                "message": item.get("message"),
            }
            for item in alerts
        ],
    }


def format_text(payload: dict[str, Any]) -> str:
    lines = [
        f"AI-OPS alerts on {payload['host']}: {payload['alert_count']}",
    ]
    for alert in payload["alerts"]:
        lines.append(
            f"[{str(alert.get('severity', 'info')).upper()}] "
            f"{alert.get('message')} ({alert.get('report')})"
        )
    return "\n".join(lines)


def send_stdout(payload: dict[str, Any]) -> dict[str, Any]:
    print(format_text(payload))
    return {"type": "stdout", "success": True}


def send_webhook(channel: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    url_env = str(channel["url_env"])
    token_env = str(channel["token_env"])
    url = os.environ.get(url_env, "").strip()
    if not url:
        return {
            "type": "webhook",
            "success": False,
            "error": f"environment variable {url_env} is empty",
        }

    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return {"type": "webhook", "success": False, "error": "invalid webhook URL"}
    if parsed.scheme != "https" and not bool(channel.get("allow_http")):
        return {
            "type": "webhook",
            "success": False,
            "error": "plain HTTP webhook is disabled",
        }

    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "ai-ops-standard-notifier/1.0",
    }
    token = os.environ.get(token_env, "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(
            request, timeout=int(channel.get("timeout_seconds", 10))
        ) as response:
            status = int(response.status)
            response.read(4096)
    except urllib.error.HTTPError as exc:
        exc.read(4096)
        return {
            "type": "webhook",
            "success": False,
            "status": int(exc.code),
            "error": "webhook returned an HTTP error",
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "type": "webhook",
            "success": False,
            "error": str(exc),
        }
    return {
        "type": "webhook",
        "success": 200 <= status < 300,
        "status": status,
    }


def dispatch(
    channels: list[dict[str, Any]], payload: dict[str, Any]
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for channel in channels:
        if not channel.get("enabled"):
            continue
        if channel["type"] == "stdout":
            results.append(send_stdout(payload))
        elif channel["type"] == "webhook":
            results.append(send_webhook(channel, payload))
    return results


def append_audit_event(root: Path, event: dict[str, Any]) -> None:
    audit_dir = root / ".aiops-audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / "events.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    path.chmod(0o640)


def resolve_under_root(root: Path, value: str, default: str) -> Path:
    path = Path(value or default).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"root directory does not exist: {root}")
    config_path = Path(args.config).expanduser().resolve()
    config = validate_config(load_json(config_path))
    state_path = resolve_under_root(root, args.state, ".aiops-notifications/state.json")
    output_path = resolve_under_root(root, args.output, "notification-status.json")

    store = ReportStore(root)
    alerts = store.alerts()
    state = load_state(state_path)
    eligible, pending, suppressed = select_alerts(
        alerts,
        state,
        minimum_severity=config["minimum_severity"],
        cooldown_seconds=config["cooldown_seconds"],
    )

    enabled_channels = [item for item in config["channels"] if item.get("enabled")]
    payload = notification_payload(pending)
    channel_results: list[dict[str, Any]] = []
    success = True
    dispatched = 0

    if args.apply and pending:
        if not enabled_channels:
            success = False
            channel_results.append(
                {"type": "none", "success": False, "error": "no enabled channels"}
            )
        else:
            channel_results = dispatch(enabled_channels, payload)
            success = bool(channel_results) and all(
                result.get("success") is True for result in channel_results
            )
        if success:
            sent_at = now()
            state_sent = state.setdefault("sent", {})
            for item in pending:
                state_sent[item["fingerprint"]] = sent_at
            dispatched = len(pending)

            cutoff = time.time() - int(config["state_retention_seconds"])
            state["sent"] = {
                fingerprint: timestamp
                for fingerprint, timestamp in state_sent.items()
                if isinstance(timestamp, str)
                and (
                    parse_time(timestamp) >= cutoff
                    if timestamp
                    else False
                )
            }
            state["updated_at"] = sent_at
            write_json_atomic(state_path, state, mode=0o600)

    status = {
        "schema_version": "1.0",
        "generated_at": now(),
        "mode": "apply" if args.apply else "dry-run",
        "success": success,
        "minimum_severity": config["minimum_severity"],
        "cooldown_seconds": config["cooldown_seconds"],
        "active_alerts": len(alerts),
        "eligible_alerts": len(eligible),
        "pending_alerts": len(pending),
        "suppressed_alerts": len(suppressed),
        "dispatched_alerts": dispatched,
        "enabled_channels": [item["type"] for item in enabled_channels],
        "channel_results": channel_results,
        "pending": [
            {
                "id": item.get("id"),
                "severity": item.get("severity"),
                "report": item.get("report"),
                "message": item.get("message"),
            }
            for item in pending
        ],
    }
    write_json_atomic(output_path, status)
    append_audit_event(
        root,
        {
            "schema_version": "1.0",
            "event_id": hashlib.sha256(
                f"{status['generated_at']}:{os.getpid()}".encode("utf-8")
            ).hexdigest()[:32],
            "event_type": "notification-dispatch",
            "occurred_at": status["generated_at"],
            "mode": status["mode"],
            "success": success,
            "active_alerts": len(alerts),
            "pending_alerts": len(pending),
            "dispatched_alerts": dispatched,
            "channels": status["enabled_channels"],
        },
    )
    return (0 if success else 2), status


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--root", default=str(PROJECT_ROOT))
    result.add_argument("--config", required=True)
    result.add_argument("--state", default=".aiops-notifications/state.json")
    result.add_argument("--output", default="notification-status.json")
    result.add_argument("--lock-file", default=".aiops-notifications/dispatch.lock")
    result.add_argument("--apply", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    root = Path(args.root).expanduser().resolve()
    lock_path = resolve_under_root(root, args.lock_file, ".aiops-notifications/dispatch.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock_path.open("a+", encoding="utf-8") as stream:
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print("AI-OPS notification dispatch is already running.")
                return 0
            code, _status = run(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Notification dispatch failed: {exc}", file=sys.stderr)
        return 2
    print(resolve_under_root(root, args.output, "notification-status.json"))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
