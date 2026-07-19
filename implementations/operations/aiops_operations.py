#!/usr/bin/env python3
"""AI-OPS reference implementation for planning, backup, execution, verification and rollback."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "0.1.0"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(data: dict[str, Any], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def classify_risk(actions: list[dict[str, Any]]) -> str:
    levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    level = 1
    for action in actions:
        kind = action.get("type")
        target = str(action.get("path", ""))
        if kind in {"delete", "command"}:
            level = max(level, 3)
        if target.startswith(("/etc/", "/boot/", "/usr/", "/var/lib/")):
            level = max(level, 3)
        if action.get("service_restart") or action.get("production"):
            level = max(level, 3)
        if action.get("safety_critical"):
            level = 4
    return next(k for k, v in levels.items() if v == level)


def make_plan(args: argparse.Namespace) -> int:
    discovery = load(args.discovery)
    request = load(args.request)
    actions = request.get("actions", [])
    if not isinstance(actions, list) or not actions:
        raise ValueError("request.actions must be a non-empty list")
    risk = classify_risk(actions)
    approval_required = risk in {"high", "critical"}
    targets = sorted({str(a.get("path")) for a in actions if a.get("path")})
    plan = {
        "schema_version": "1.0",
        "plan_id": request.get("plan_id") or f"plan-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "created_at": now(),
        "tool": {"name": "aiops_operations", "version": VERSION},
        "intent": request.get("intent", ""),
        "discovery_report": str(Path(args.discovery).resolve()),
        "discovery_host": discovery.get("host", {}),
        "risk": {"level": risk, "approval_required": approval_required},
        "preconditions": request.get("preconditions", []),
        "actions": actions,
        "backup": {"required": bool(targets), "targets": targets},
        "verification": request.get("verification", []),
        "rollback": {"strategy": "restore-backup", "targets": targets},
        "status": "awaiting-approval" if approval_required else "ready",
    }
    dump(plan, args.output)
    print(args.output)
    return 0


def make_backup(args: argparse.Namespace) -> int:
    plan = load(args.plan)
    root = Path(args.backup_root).resolve() / plan["plan_id"]
    root.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for raw in plan.get("backup", {}).get("targets", []):
        source = Path(raw)
        entry: dict[str, Any] = {"source": str(source), "existed": source.exists()}
        if source.exists():
            rel = str(source.resolve()).lstrip("/")
            destination = root / "files" / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=True)
                entry.update({"type": "directory", "backup": str(destination)})
            else:
                shutil.copy2(source, destination, follow_symlinks=False)
                entry.update({"type": "file", "backup": str(destination), "sha256": sha256(source)})
        entries.append(entry)
    manifest = {
        "schema_version": "1.0",
        "plan_id": plan["plan_id"],
        "created_at": now(),
        "backup_root": str(root),
        "entries": entries,
        "complete": True,
    }
    manifest_path = root / "backup-manifest.json"
    dump(manifest, manifest_path)
    print(manifest_path)
    return 0


def check_approval(plan: dict[str, Any], args: argparse.Namespace) -> None:
    if plan.get("risk", {}).get("approval_required") and not args.approved:
        raise PermissionError("high-risk plan requires --approved")


def execute(args: argparse.Namespace) -> int:
    plan = load(args.plan)
    check_approval(plan, args)
    report: dict[str, Any] = {
        "plan_id": plan["plan_id"], "started_at": now(), "apply": args.apply,
        "results": [], "success": True,
    }
    for action in plan.get("actions", []):
        result = {"action": action, "status": "planned" if not args.apply else "pending"}
        try:
            if args.apply:
                kind = action["type"]
                if kind == "mkdir":
                    Path(action["path"]).mkdir(parents=True, exist_ok=True)
                elif kind == "write_file":
                    p = Path(action["path"])
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(str(action.get("content", "")), encoding="utf-8")
                elif kind == "copy_file":
                    src, dst = Path(action["source"]), Path(action["path"])
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                elif kind == "delete":
                    p = Path(action["path"])
                    if p.is_dir(): shutil.rmtree(p)
                    elif p.exists() or p.is_symlink(): p.unlink()
                elif kind == "command":
                    argv = action.get("argv")
                    if not isinstance(argv, list) or not argv:
                        raise ValueError("command action requires argv array")
                    cp = subprocess.run(argv, text=True, capture_output=True, timeout=int(action.get("timeout", 60)), check=False)
                    result.update({"returncode": cp.returncode, "stdout": cp.stdout[-4000:], "stderr": cp.stderr[-4000:]})
                    if cp.returncode != 0: raise RuntimeError(f"command failed: {cp.returncode}")
                else:
                    raise ValueError(f"unsupported action type: {kind}")
                result["status"] = "completed"
        except Exception as exc:
            result.update({"status": "failed", "error": str(exc)})
            report["success"] = False
            report["results"].append(result)
            if not args.continue_on_error: break
        else:
            report["results"].append(result)
    report["finished_at"] = now()
    dump(report, args.output)
    print(args.output)
    return 0 if report["success"] else 2


def verify(args: argparse.Namespace) -> int:
    plan = load(args.plan)
    checks = plan.get("verification", [])
    results: list[dict[str, Any]] = []
    passed = True
    for check in checks:
        kind = check.get("type")
        result = {"check": check, "passed": False}
        try:
            if kind == "exists":
                result["passed"] = Path(check["path"]).exists()
            elif kind == "not_exists":
                result["passed"] = not Path(check["path"]).exists()
            elif kind == "file_contains":
                result["passed"] = str(check["text"]) in Path(check["path"]).read_text(encoding="utf-8")
            elif kind == "sha256":
                result["actual"] = sha256(Path(check["path"]))
                result["passed"] = result["actual"] == check["expected"]
            elif kind == "command":
                argv = check.get("argv")
                cp = subprocess.run(argv, text=True, capture_output=True, timeout=int(check.get("timeout", 30)), check=False)
                result.update({"returncode": cp.returncode, "stdout": cp.stdout[-4000:], "stderr": cp.stderr[-4000:]})
                result["passed"] = cp.returncode == int(check.get("expected_returncode", 0))
            else:
                result["error"] = f"unsupported verification type: {kind}"
        except Exception as exc:
            result["error"] = str(exc)
        passed = passed and bool(result["passed"])
        results.append(result)
    report = {"plan_id": plan["plan_id"], "verified_at": now(), "passed": passed, "results": results}
    dump(report, args.output)
    print(args.output)
    return 0 if passed else 3


def rollback(args: argparse.Namespace) -> int:
    manifest = load(args.manifest)
    results: list[dict[str, Any]] = []
    success = True
    for entry in reversed(manifest.get("entries", [])):
        source = Path(entry["source"])
        result = {"source": str(source), "status": "pending"}
        try:
            if entry.get("existed"):
                backup = Path(entry["backup"])
                source.parent.mkdir(parents=True, exist_ok=True)
                if entry.get("type") == "directory":
                    if source.exists(): shutil.rmtree(source)
                    shutil.copytree(backup, source, symlinks=True)
                else:
                    shutil.copy2(backup, source, follow_symlinks=False)
            else:
                if source.is_dir(): shutil.rmtree(source)
                elif source.exists() or source.is_symlink(): source.unlink()
            result["status"] = "restored"
        except Exception as exc:
            success = False
            result.update({"status": "failed", "error": str(exc)})
        results.append(result)
    report = {"plan_id": manifest.get("plan_id"), "rolled_back_at": now(), "success": success, "results": results}
    dump(report, args.output)
    print(args.output)
    return 0 if success else 4


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    x = sub.add_parser("plan"); x.add_argument("--discovery", required=True); x.add_argument("--request", required=True); x.add_argument("--output", default="operation-plan.json"); x.set_defaults(func=make_plan)
    x = sub.add_parser("backup"); x.add_argument("--plan", required=True); x.add_argument("--backup-root", default=".aiops-backups"); x.set_defaults(func=make_backup)
    x = sub.add_parser("execute"); x.add_argument("--plan", required=True); x.add_argument("--output", default="execution-report.json"); x.add_argument("--apply", action="store_true"); x.add_argument("--approved", action="store_true"); x.add_argument("--continue-on-error", action="store_true"); x.set_defaults(func=execute)
    x = sub.add_parser("verify"); x.add_argument("--plan", required=True); x.add_argument("--output", default="verification-report.json"); x.set_defaults(func=verify)
    x = sub.add_parser("rollback"); x.add_argument("--manifest", required=True); x.add_argument("--output", default="rollback-report.json"); x.set_defaults(func=rollback)
    return p


def main() -> int:
    try:
        args = parser().parse_args()
        return int(args.func(args))
    except (OSError, ValueError, KeyError, PermissionError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
