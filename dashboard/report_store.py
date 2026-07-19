#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

MAX_REPORT_BYTES = 10 * 1024 * 1024
MAX_REPORTS = 500
FRESHNESS_SECONDS = {
    "refresh": 45 * 60,
    "discovery": 45 * 60,
    "capabilities": 45 * 60,
    "compliance": 45 * 60,
}
IGNORED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".aiops-audit",
}


def _iso_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _age_seconds(timestamp: float) -> int:
    return max(0, int(datetime.now(timezone.utc).timestamp() - timestamp))


def classify_report(name: str, data: Any) -> str:
    lowered = name.lower()
    if isinstance(data, dict):
        if "collectors" in data and "report_id" in data:
            return "discovery"
        if "agents" in data and "mcp" in data:
            return "capabilities"
        if (
            "refresh-status" in lowered
            or (
                "steps" in data
                and "success" in data
                and "reports" in data
                and "project_root" in data
            )
        ):
            return "refresh"
        if (
            isinstance(data.get("summary"), dict)
            and "results" in data
            and {"passed", "failed"} <= set(data["summary"])
        ):
            return "compliance"
        if "plan_id" in data and "actions" in data and "risk" in data:
            return "plan"
        if "backup_root" in data and "entries" in data:
            return "backup"
        if "plan_id" in data and "apply" in data and "results" in data:
            return "execution"
        if "plan_id" in data and "verified_at" in data and "passed" in data:
            return "verification"
        if "plan_id" in data and "rolled_back_at" in data and "success" in data:
            return "rollback"

    filename_markers = (
        ("discovery", "discovery"),
        ("capability", "capabilities"),
        ("registry", "capabilities"),
        ("refresh-status", "refresh"),
        ("compliance", "compliance"),
        ("operation-plan", "plan"),
        ("backup-manifest", "backup"),
        ("execution", "execution"),
        ("verification", "verification"),
        ("rollback", "rollback"),
    )
    for marker, category in filename_markers:
        if marker in lowered:
            return category
    return "other"


def summarize_report(category: str, data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"items": len(data) if isinstance(data, list) else 1}

    if category == "discovery":
        collectors = data.get("collectors", {})
        errors = data.get("errors", [])
        effective_user = data.get("effective_user", {})
        return {
            "collectors": len(collectors) if isinstance(collectors, dict) else 0,
            "errors": len(errors) if isinstance(errors, list) else 0,
            "user": effective_user.get("name") if isinstance(effective_user, dict) else None,
            "generated_at": data.get("generated_at"),
        }

    if category == "capabilities":
        agents = data.get("agents", [])
        installed = 0
        if isinstance(agents, list):
            installed = sum(
                1
                for item in agents
                if isinstance(item, dict) and item.get("installed")
            )
        candidates = data.get("mcp", {}).get("config_candidates", [])
        return {
            "agents_total": len(agents) if isinstance(agents, list) else 0,
            "agents_installed": installed,
            "mcp_configs": len(candidates) if isinstance(candidates, list) else 0,
            "generated_at": data.get("generated_at"),
        }

    if category == "refresh":
        steps = data.get("steps", [])
        failed_steps = 0
        if isinstance(steps, list):
            failed_steps = sum(
                1
                for step in steps
                if isinstance(step, dict) and step.get("accepted") is False
            )
        return {
            "success": data.get("success"),
            "duration_seconds": data.get("duration_seconds"),
            "reports": len(data.get("reports", [])),
            "failed_steps": failed_steps,
            "generated_at": data.get("generated_at"),
        }

    if category == "compliance":
        summary = data.get("summary", {})
        return {
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "generated_at": data.get("generated_at"),
        }

    if category == "plan":
        risk = data.get("risk", {})
        return {
            "plan_id": data.get("plan_id"),
            "status": data.get("status"),
            "risk": risk.get("level") if isinstance(risk, dict) else None,
            "actions": len(data.get("actions", [])),
        }

    if category == "backup":
        return {
            "plan_id": data.get("plan_id"),
            "entries": len(data.get("entries", [])),
            "complete": data.get("complete"),
            "created_at": data.get("created_at"),
        }

    if category == "execution":
        return {
            "plan_id": data.get("plan_id"),
            "mode": "apply" if data.get("apply") else "dry-run",
            "success": data.get("success"),
            "actions": len(data.get("results", [])),
            "finished_at": data.get("finished_at"),
        }

    if category == "verification":
        return {
            "plan_id": data.get("plan_id"),
            "passed": data.get("passed"),
            "checks": len(data.get("results", [])),
            "verified_at": data.get("verified_at"),
        }

    if category == "rollback":
        return {
            "plan_id": data.get("plan_id"),
            "success": data.get("success"),
            "entries": len(data.get("results", [])),
            "rolled_back_at": data.get("rolled_back_at"),
        }

    return {"keys": len(data)}


class ReportStore:
    def __init__(
        self,
        root: str | Path,
        *,
        max_report_bytes: int = MAX_REPORT_BYTES,
        max_reports: int = MAX_REPORTS,
        freshness_seconds: dict[str, int] | None = None,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.max_report_bytes = max_report_bytes
        self.max_reports = max_reports
        self.freshness_seconds = dict(FRESHNESS_SECONDS)
        if freshness_seconds:
            self.freshness_seconds.update(freshness_seconds)

    def _relative_name(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _is_allowed_path(self, path: Path) -> bool:
        try:
            resolved = path.resolve(strict=True)
            relative = resolved.relative_to(self.root)
        except (OSError, ValueError):
            return False
        return (
            resolved.is_file()
            and not path.is_symlink()
            and resolved.suffix.lower() == ".json"
            and not any(part in IGNORED_PARTS for part in relative.parts)
        )

    def iter_paths(self) -> list[Path]:
        paths: list[Path] = []
        for path in self.root.rglob("*.json"):
            if self._is_allowed_path(path):
                paths.append(path.resolve())
        paths.sort(key=lambda item: self._relative_name(item))
        return paths[: self.max_reports]

    def resolve_name(self, name: str) -> Path:
        if "\\" in name:
            raise ValueError("invalid report name")
        pure = PurePosixPath(name)
        if (
            pure.is_absolute()
            or not pure.parts
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise ValueError("invalid report name")
        candidate = self.root.joinpath(*pure.parts)
        if not self._is_allowed_path(candidate):
            raise FileNotFoundError(name)
        return candidate.resolve()

    def _read_path(self, path: Path) -> tuple[Any | None, str | None]:
        try:
            size = path.stat().st_size
        except OSError as exc:
            return None, str(exc)
        if size > self.max_report_bytes:
            return None, f"report exceeds {self.max_report_bytes} byte limit"
        try:
            return json.loads(path.read_text(encoding="utf-8")), None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return None, str(exc)

    def metadata(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        data, error = self._read_path(path)
        category = classify_report(self._relative_name(path), data)
        age_seconds = _age_seconds(stat.st_mtime)
        threshold = self.freshness_seconds.get(category)
        result: dict[str, Any] = {
            "name": self._relative_name(path),
            "category": category,
            "size": stat.st_size,
            "modified_at": _iso_timestamp(stat.st_mtime),
            "age_seconds": age_seconds,
            "stale": bool(threshold is not None and age_seconds > threshold),
        }
        if threshold is not None:
            result["freshness_limit_seconds"] = threshold
        if error:
            result["error"] = error
        else:
            result["summary"] = summarize_report(category, data)
        return result

    def list_reports(self) -> list[dict[str, Any]]:
        return [self.metadata(path) for path in self.iter_paths()]

    def get_report(self, name: str) -> dict[str, Any]:
        path = self.resolve_name(name)
        metadata = self.metadata(path)
        data, error = self._read_path(path)
        if error:
            metadata["error"] = error
        else:
            metadata["data"] = data
        return metadata

    def alerts(
        self, reports: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        reports = reports if reports is not None else self.list_reports()
        alerts: list[dict[str, Any]] = []

        def add(
            report: dict[str, Any], alert_type: str, severity: str, message: str
        ) -> None:
            alerts.append(
                {
                    "id": f"{alert_type}:{report['name']}",
                    "type": alert_type,
                    "severity": severity,
                    "report": report["name"],
                    "category": report["category"],
                    "message": message,
                }
            )

        for report in reports:
            summary = report.get("summary", {})
            if report.get("error"):
                add(report, "invalid-report", "critical", "Izveštaj nije moguće učitati kao validan JSON.")
                continue
            if report.get("stale"):
                minutes = int(report.get("age_seconds", 0)) // 60
                add(report, "stale-report", "warning", f"Izveštaj nije osvežen {minutes} minuta.")
            category = report.get("category")
            if category == "refresh" and summary.get("success") is False:
                add(report, "refresh-failed", "critical", "Poslednje automatsko osvežavanje nije uspelo.")
            elif category == "compliance" and int(summary.get("failed", 0) or 0) > 0:
                add(report, "compliance-failed", "warning", f"Neusaglašeni zahtevi: {summary.get('failed')}.")
            elif category == "execution" and summary.get("success") is False:
                add(report, "execution-failed", "critical", "Izvršenje plana nije uspelo.")
            elif category == "verification" and summary.get("passed") is False:
                add(report, "verification-failed", "critical", "Verifikacija plana nije prošla.")
            elif category == "rollback" and summary.get("success") is False:
                add(report, "rollback-failed", "critical", "Rollback nije uspeo.")
            elif category == "backup" and summary.get("complete") is False:
                add(report, "backup-incomplete", "critical", "Backup manifest nije kompletan.")

        priority = {"critical": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda item: (priority.get(item["severity"], 9), item["report"], item["type"]))
        return alerts

    def summary(self) -> dict[str, Any]:
        reports = self.list_reports()
        categories: dict[str, int] = {}
        invalid = 0
        stale = 0
        compliance_passed = 0
        compliance_failed = 0
        for report in reports:
            category = str(report["category"])
            categories[category] = categories.get(category, 0) + 1
            if report.get("error"):
                invalid += 1
            if report.get("stale"):
                stale += 1
            if category == "compliance":
                summary = report.get("summary", {})
                compliance_passed += int(summary.get("passed", 0) or 0)
                compliance_failed += int(summary.get("failed", 0) or 0)

        alerts = self.alerts(reports)
        alert_counts = {"critical": 0, "warning": 0, "info": 0}
        for alert in alerts:
            severity = str(alert.get("severity", "info"))
            alert_counts[severity] = alert_counts.get(severity, 0) + 1

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "root": str(self.root),
            "report_count": len(reports),
            "invalid_reports": invalid,
            "stale_reports": stale,
            "categories": categories,
            "compliance": {
                "passed": compliance_passed,
                "failed": compliance_failed,
            },
            "alerts": {
                "total": len(alerts),
                **alert_counts,
            },
        }

    def ready(self) -> bool:
        return self.root.is_dir() and self.root.exists()
