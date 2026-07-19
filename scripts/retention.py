#!/usr/bin/env python3
"""Plan or apply retention for AI-OPS backups and rotated audit logs."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_candidate(root: Path, path: Path) -> bool:
    try:
        resolved_root = root.resolve(strict=True)
        resolved = path.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError):
        return False
    return path != root and not path.is_symlink()


def _candidate(path: Path, root: Path, kind: str, current_time: float) -> dict[str, Any]:
    stat = path.stat()
    size = 0
    if path.is_dir():
        for child in path.rglob("*"):
            try:
                if child.is_file() and not child.is_symlink():
                    size += child.stat().st_size
            except OSError:
                continue
    else:
        size = stat.st_size
    return {
        "kind": kind,
        "path": path.relative_to(root).as_posix(),
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "age_days": round(max(0.0, current_time - stat.st_mtime) / 86400, 2),
        "bytes": size,
    }


def plan_retention(
    root: str | Path,
    *,
    backup_days: int = 30,
    audit_days: int = 90,
    current_time: float | None = None,
) -> dict[str, Any]:
    if backup_days < 1 or audit_days < 1:
        raise ValueError("retention days must be at least 1")

    root_path = Path(root).expanduser().resolve(strict=True)
    current = time.time() if current_time is None else current_time
    backup_cutoff = current - backup_days * 86400
    audit_cutoff = current - audit_days * 86400
    candidates: list[dict[str, Any]] = []

    backup_root = root_path / ".aiops-backups"
    if backup_root.is_dir() and not backup_root.is_symlink():
        for path in sorted(backup_root.iterdir()):
            try:
                if (
                    path.is_dir()
                    and _safe_candidate(root_path, path)
                    and path.stat().st_mtime < backup_cutoff
                ):
                    candidates.append(_candidate(path, root_path, "backup", current))
            except OSError:
                continue

    audit_root = root_path / ".aiops-audit"
    if audit_root.is_dir() and not audit_root.is_symlink():
        for path in sorted(audit_root.glob("events.jsonl.*")):
            try:
                if (
                    path.is_file()
                    and _safe_candidate(root_path, path)
                    and path.stat().st_mtime < audit_cutoff
                ):
                    candidates.append(_candidate(path, root_path, "audit-rotation", current))
            except OSError:
                continue

    candidates.sort(key=lambda item: (item["kind"], item["path"]))
    return {
        "schema_version": "1.0",
        "generated_at": now(),
        "root": str(root_path),
        "policy": {"backup_days": backup_days, "audit_days": audit_days},
        "candidate_count": len(candidates),
        "candidate_bytes": sum(int(item["bytes"]) for item in candidates),
        "candidates": candidates,
    }


def apply_retention(plan: dict[str, Any]) -> dict[str, Any]:
    root = Path(str(plan["root"])).resolve(strict=True)
    results: list[dict[str, Any]] = []
    success = True

    for item in plan.get("candidates", []):
        relative = Path(str(item["path"]))
        target = root / relative
        result = {"path": relative.as_posix(), "kind": item.get("kind"), "status": "pending"}
        try:
            if not _safe_candidate(root, target):
                raise ValueError("candidate failed safety validation")
            if target.is_dir():
                shutil.rmtree(target)
            elif target.is_file():
                target.unlink()
            else:
                raise FileNotFoundError(target)
            result["status"] = "deleted"
        except (OSError, ValueError) as exc:
            success = False
            result.update({"status": "failed", "error": str(exc)})
        results.append(result)

    return {
        "schema_version": "1.0",
        "generated_at": now(),
        "root": str(root),
        "success": success,
        "deleted": sum(1 for item in results if item["status"] == "deleted"),
        "failed": sum(1 for item in results if item["status"] == "failed"),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--backup-days", type=int, default=30)
    parser.add_argument("--audit-days", type=int, default=90)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        plan = plan_retention(
            args.root,
            backup_days=args.backup_days,
            audit_days=args.audit_days,
        )
        payload = apply_retention(plan) if args.apply else {**plan, "mode": "dry-run"}
    except (OSError, ValueError, KeyError) as exc:
        print(f"retention failed: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(args.output)
    else:
        print(rendered, end="")
    return 0 if payload.get("success", True) else 3


if __name__ == "__main__":
    raise SystemExit(main())
