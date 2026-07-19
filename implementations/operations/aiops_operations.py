#!/usr/bin/env python3
"""AI-OPS reference implementation for planning, backup, execution, verification and rollback."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "0.2.2"
SUPPORTED_ACTIONS = {"mkdir", "write_file", "copy_file", "delete", "command"}
PLAN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
PROTECTED_EXACT_TARGETS = {
    "/",
    "/boot",
    "/dev",
    "/etc",
    "/home",
    "/opt",
    "/proc",
    "/root",
    "/run",
    "/sys",
    "/tmp",
    "/usr",
    "/var",
    "/var/lib",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def dump(data: dict[str, Any], path: str | Path, mode: int = 0o600) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def canonical_digest(data: dict[str, Any]) -> str:
    encoded = json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_exists(path: Path) -> bool:
    return os.path.lexists(path)


def snapshot_type(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "file"
    raise ValueError(f"unsupported filesystem object: {path}")


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    digest.update(b"directory\0")
    for path in sorted(
        root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
    ):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        if path.is_symlink():
            digest.update(
                b"L\0"
                + relative
                + b"\0"
                + os.readlink(path).encode("utf-8")
                + b"\0"
            )
        elif path.is_dir():
            digest.update(b"D\0" + relative + b"\0")
        elif path.is_file():
            digest.update(
                b"F\0"
                + relative
                + b"\0"
                + sha256(path).encode("ascii")
                + b"\0"
            )
        else:
            raise ValueError(f"unsupported object inside directory: {path}")
    return digest.hexdigest()


def snapshot_digest(path: Path) -> str:
    kind = snapshot_type(path)
    if kind == "symlink":
        return hashlib.sha256(
            ("symlink\0" + os.readlink(path)).encode("utf-8")
        ).hexdigest()
    if kind == "directory":
        return tree_digest(path)
    return sha256(path)


def remove_path(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path_exists(path):
        path.unlink()


def copy_snapshot(source: Path, destination: Path) -> str:
    kind = snapshot_type(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if kind == "symlink":
        os.symlink(os.readlink(source), destination)
    elif kind == "directory":
        shutil.copytree(source, destination, symlinks=True)
    else:
        shutil.copy2(source, destination, follow_symlinks=False)
    return kind


def validate_plan_id(value: Any) -> str:
    plan_id = str(value or "")
    if not PLAN_ID_PATTERN.fullmatch(plan_id):
        raise ValueError(
            "plan_id must contain only letters, digits, dot, underscore and hyphen"
        )
    return plan_id


def validate_argv(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty argv array")
    if not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{field} must contain non-empty strings")
    return list(value)


def normalize_path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError("filesystem path must be a non-empty string")
    expanded = os.path.expanduser(value)
    return os.path.abspath(os.path.normpath(expanded))


def normalize_target_path(value: Any) -> str:
    normalized = normalize_path(value)
    if normalized in PROTECTED_EXACT_TARGETS:
        raise ValueError(f"operation target is a protected system root: {normalized}")
    return normalized


def normalize_action(action: Any) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise ValueError("every action must be an object")
    normalized = json.loads(json.dumps(action))
    kind = normalized.get("type")
    if kind not in SUPPORTED_ACTIONS:
        raise ValueError(f"unsupported action type: {kind}")

    if kind == "command":
        normalized["argv"] = validate_argv(normalized.get("argv"), "command argv")
        normalized["rollback_argv"] = validate_argv(
            normalized.get("rollback_argv"), "command rollback_argv"
        )
        timeout = int(normalized.get("timeout", 60))
        rollback_timeout = int(normalized.get("rollback_timeout", timeout))
        if not 1 <= timeout <= 3600 or not 1 <= rollback_timeout <= 3600:
            raise ValueError("command timeouts must be between 1 and 3600 seconds")
        normalized["timeout"] = timeout
        normalized["rollback_timeout"] = rollback_timeout
        backup_targets = normalized.get("backup_targets", [])
        if not isinstance(backup_targets, list):
            raise ValueError("command backup_targets must be an array")
        normalized["backup_targets"] = [
            normalize_target_path(item) for item in backup_targets
        ]
        return normalized

    normalized["path"] = normalize_target_path(normalized.get("path"))
    if kind == "write_file":
        if "content" in normalized and "content_from" in normalized:
            raise ValueError("write_file accepts content or content_from, not both")
        if "content_from" in normalized:
            normalized["content_from"] = normalize_path(normalized["content_from"])
    elif kind == "copy_file":
        normalized["source"] = normalize_path(normalized.get("source"))
    return normalized


def normalize_check(check: Any) -> str | dict[str, Any]:
    if isinstance(check, str):
        if not check.strip():
            raise ValueError("manual check text must not be empty")
        return check
    if not isinstance(check, dict):
        raise ValueError("check must be a string or object")
    normalized = json.loads(json.dumps(check))
    kind = normalized.get("type")
    if kind in {"exists", "not_exists", "file_contains", "sha256", "writable"}:
        normalized["path"] = normalize_path(normalized.get("path"))
    elif kind == "command":
        normalized["argv"] = validate_argv(normalized.get("argv"), "check argv")
        timeout = int(normalized.get("timeout", 30))
        if not 1 <= timeout <= 3600:
            raise ValueError("check timeout must be between 1 and 3600 seconds")
        normalized["timeout"] = timeout
    else:
        raise ValueError(f"unsupported check type: {kind}")
    return normalized


def action_targets(actions: list[dict[str, Any]]) -> list[str]:
    targets: set[str] = set()
    for action in actions:
        if action["type"] == "command":
            targets.update(str(item) for item in action.get("backup_targets", []))
        else:
            targets.add(str(action["path"]))
    return sorted(targets)


def classify_risk(actions: list[dict[str, Any]]) -> str:
    levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    level = 1
    for action in actions:
        kind = action.get("type")
        targets = (
            action.get("backup_targets", [])
            if kind == "command"
            else [action.get("path", "")]
        )
        if kind in {"delete", "command"}:
            level = max(level, 3)
        if any(
            str(target).startswith(("/etc/", "/boot/", "/usr/", "/var/lib/"))
            for target in targets
        ):
            level = max(level, 3)
        if action.get("service_restart") or action.get("production"):
            level = max(level, 3)
        if action.get("safety_critical"):
            level = 4
    return next(name for name, value in levels.items() if value == level)


def validate_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    validate_plan_id(plan.get("plan_id"))
    raw_actions = plan.get("actions", [])
    if not isinstance(raw_actions, list) or not raw_actions:
        raise ValueError("plan.actions must be a non-empty list")
    actions = [normalize_action(action) for action in raw_actions]
    expected_targets = action_targets(actions)
    backup = plan.get("backup", {})
    if bool(backup.get("required")) != bool(expected_targets):
        raise ValueError("plan backup.required does not match action targets")
    if sorted(str(item) for item in backup.get("targets", [])) != expected_targets:
        raise ValueError("plan backup targets do not match action targets")
    return actions


def make_plan(args: argparse.Namespace) -> int:
    discovery = load(args.discovery)
    request = load(args.request)
    raw_actions = request.get("actions", [])
    if not isinstance(raw_actions, list) or not raw_actions:
        raise ValueError("request.actions must be a non-empty list")
    actions = [normalize_action(action) for action in raw_actions]
    preconditions = [
        normalize_check(check) for check in request.get("preconditions", [])
    ]
    verification = [
        normalize_check(check) for check in request.get("verification", [])
    ]
    risk = classify_risk(actions)
    approval_required = risk in {"high", "critical"}
    targets = action_targets(actions)
    requested_id = request.get("plan_id")
    plan_id = validate_plan_id(
        requested_id
        or f"plan-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    plan = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "created_at": now(),
        "tool": {"name": "aiops_operations", "version": VERSION},
        "intent": request.get("intent", ""),
        "discovery_report": str(Path(args.discovery).resolve()),
        "discovery_host": discovery.get("host", {}),
        "risk": {"level": risk, "approval_required": approval_required},
        "preconditions": preconditions,
        "actions": actions,
        "backup": {"required": bool(targets), "targets": targets},
        "verification": verification,
        "rollback": {
            "strategy": "restore-verified-backup-and-command-rollback",
            "targets": targets,
            "command_rollback_required": any(
                action["type"] == "command" for action in actions
            ),
        },
        "status": "awaiting-approval" if approval_required else "ready",
    }
    dump(plan, args.output)
    print(args.output)
    return 0


def make_backup(args: argparse.Namespace) -> int:
    plan = load(args.plan)
    actions = validate_plan(plan)
    plan_id = validate_plan_id(plan["plan_id"])
    root = Path(args.backup_root).expanduser().resolve() / plan_id
    targets = action_targets(actions)
    for raw in targets:
        source = Path(raw)
        if root == source or source in root.parents:
            raise ValueError(f"backup root is inside operation target: {source}")
    if root.exists() and any(root.iterdir()):
        if not args.replace:
            raise FileExistsError(
                f"backup directory already contains data: {root}; use --replace explicitly"
            )
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)

    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, raw in enumerate(targets):
        source = Path(raw)
        existed = path_exists(source)
        entry: dict[str, Any] = {
            "source": str(source),
            "existed": existed,
            "status": "pending",
        }
        try:
            if existed:
                kind = snapshot_type(source)
                destination = root / "objects" / f"{index:04d}"
                digest_before = snapshot_digest(source)
                copied_kind = copy_snapshot(source, destination)
                digest_after = snapshot_digest(source)
                backup_digest = snapshot_digest(destination)
                if kind != copied_kind or not (
                    digest_before == digest_after == backup_digest
                ):
                    raise RuntimeError("source changed while backup was being created")
                entry.update(
                    {
                        "type": kind,
                        "backup": str(destination),
                        "source_digest": digest_after,
                        "backup_digest": backup_digest,
                    }
                )
            entry["status"] = "completed"
        except Exception as exc:
            entry.update({"status": "failed", "error": str(exc)})
            errors.append(f"{source}: {exc}")
        entries.append(entry)

    complete = not errors and all(
        entry["status"] == "completed" for entry in entries
    )
    manifest = {
        "schema_version": "1.1",
        "plan_id": plan_id,
        "plan_digest": canonical_digest(plan),
        "created_at": now(),
        "backup_root": str(root),
        "risk": plan.get("risk", {}),
        "targets": targets,
        "entries": entries,
        "complete": complete,
        "errors": errors,
    }
    manifest_path = root / "backup-manifest.json"
    dump(manifest, manifest_path)
    print(manifest_path)
    return 0 if complete else 2


def validate_manifest(
    plan: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    actions = validate_plan(plan)
    if manifest.get("complete") is not True:
        raise PermissionError("backup manifest is incomplete")
    if manifest.get("plan_id") != plan.get("plan_id"):
        raise PermissionError("backup manifest plan_id does not match plan")
    if manifest.get("plan_digest") != canonical_digest(plan):
        raise PermissionError("plan changed after backup creation")

    expected_targets = action_targets(actions)
    manifest_targets = sorted(str(item) for item in manifest.get("targets", []))
    if manifest_targets != expected_targets:
        raise PermissionError("backup manifest target set does not match plan")
    entries = manifest.get("entries", [])
    if not isinstance(entries, list):
        raise PermissionError("backup manifest entries must be an array")
    sources = [
        str(entry.get("source")) for entry in entries if isinstance(entry, dict)
    ]
    if len(sources) != len(set(sources)) or sorted(sources) != expected_targets:
        raise PermissionError(
            "backup manifest entries do not exactly match plan targets"
        )

    verified = 0
    for entry in entries:
        if entry.get("status") != "completed":
            raise PermissionError(
                f"backup entry is not complete: {entry.get('source')}"
            )
        if entry.get("existed"):
            backup = Path(str(entry.get("backup", "")))
            if not path_exists(backup):
                raise PermissionError(f"backup object is missing: {backup}")
            if snapshot_digest(backup) != entry.get("backup_digest"):
                raise PermissionError(f"backup object digest mismatch: {backup}")
        verified += 1
    return {"verified": True, "entries": verified}


def check_approval(plan: dict[str, Any], args: argparse.Namespace) -> None:
    if plan.get("risk", {}).get("approval_required") and not args.approved:
        raise PermissionError("high-risk plan requires --approved")


def evaluate_check(
    check: str | dict[str, Any], *, manual_confirmed: bool = False
) -> dict[str, Any]:
    if isinstance(check, str):
        return {
            "check": check,
            "type": "manual",
            "passed": bool(manual_confirmed),
            "error": None
            if manual_confirmed
            else "manual precondition not confirmed",
        }

    kind = check.get("type")
    result: dict[str, Any] = {"check": check, "passed": False}
    try:
        if kind == "exists":
            result["passed"] = path_exists(Path(check["path"]))
        elif kind == "not_exists":
            result["passed"] = not path_exists(Path(check["path"]))
        elif kind == "writable":
            path = Path(check["path"])
            candidate = path if path.exists() else path.parent
            result["passed"] = candidate.exists() and os.access(candidate, os.W_OK)
        elif kind == "file_contains":
            result["passed"] = str(check["text"]) in Path(
                check["path"]
            ).read_text(encoding="utf-8")
        elif kind == "sha256":
            result["actual"] = sha256(Path(check["path"]))
            result["passed"] = result["actual"] == check["expected"]
        elif kind == "command":
            argv = validate_argv(check.get("argv"), "check argv")
            completed = subprocess.run(
                argv,
                text=True,
                capture_output=True,
                timeout=int(check.get("timeout", 30)),
                check=False,
                shell=False,
            )
            result.update(
                {
                    "returncode": completed.returncode,
                    "stdout": completed.stdout[-4000:],
                    "stderr": completed.stderr[-4000:],
                }
            )
            result["passed"] = completed.returncode == int(
                check.get("expected_returncode", 0)
            )
        else:
            result["error"] = f"unsupported check type: {kind}"
    except Exception as exc:
        result["error"] = str(exc)
    return result


def run_checks(
    checks: list[str | dict[str, Any]], *, manual_confirmed: bool = False
) -> tuple[bool, list[dict[str, Any]]]:
    results = [
        evaluate_check(check, manual_confirmed=manual_confirmed) for check in checks
    ]
    return all(result.get("passed") is True for result in results), results


def action_descriptor(action: dict[str, Any], index: int) -> dict[str, Any]:
    descriptor: dict[str, Any] = {"index": index, "type": action["type"]}
    for key in ("path", "source"):
        if key in action:
            descriptor[key] = action[key]
    if action["type"] == "command":
        descriptor["executable"] = action["argv"][0]
        descriptor["argc"] = len(action["argv"])
    return descriptor


def execute(args: argparse.Namespace) -> int:
    plan = load(args.plan)
    actions = validate_plan(plan)
    if args.apply:
        check_approval(plan, args)
    report: dict[str, Any] = {
        "schema_version": "1.1",
        "plan_id": plan["plan_id"],
        "plan_digest": canonical_digest(plan),
        "started_at": now(),
        "apply": args.apply,
        "manifest": None,
        "backup_verified": False,
        "preconditions": [],
        "results": [],
        "success": True,
    }

    if args.apply:
        preconditions_ok, precondition_results = run_checks(
            plan.get("preconditions", []),
            manual_confirmed=args.manual_preconditions_confirmed,
        )
        report["preconditions"] = precondition_results
        if not preconditions_ok:
            report["success"] = False
            report["error"] = "one or more preconditions failed"
            report["finished_at"] = now()
            dump(report, args.output)
            print(args.output)
            return 2

        if plan.get("backup", {}).get("required"):
            if not args.manifest:
                raise PermissionError("apply requires --manifest for this plan")
            manifest = load(args.manifest)
            verification = validate_manifest(plan, manifest)
            report["manifest"] = str(Path(args.manifest).resolve())
            report["backup_verified"] = bool(verification["verified"])

    for index, action in enumerate(actions):
        result: dict[str, Any] = {
            "index": index,
            "action": action_descriptor(action, index),
            "status": "planned" if not args.apply else "pending",
        }
        try:
            if args.apply:
                kind = action["type"]
                if kind == "mkdir":
                    path = Path(action["path"])
                    if path.is_symlink():
                        raise PermissionError("mkdir target is a symlink")
                    path.mkdir(parents=True, exist_ok=True)
                elif kind == "write_file":
                    path = Path(action["path"])
                    if path.is_symlink():
                        if not action.get("replace_symlink"):
                            raise PermissionError(
                                "write_file refuses symlink target without replace_symlink"
                            )
                        path.unlink()
                    path.parent.mkdir(parents=True, exist_ok=True)
                    content = (
                        Path(action["content_from"]).read_text(encoding="utf-8")
                        if "content_from" in action
                        else str(action.get("content", ""))
                    )
                    path.write_text(content, encoding="utf-8")
                elif kind == "copy_file":
                    source = Path(action["source"])
                    destination = Path(action["path"])
                    if not source.is_file() or source.is_symlink():
                        raise ValueError("copy_file source must be a regular file")
                    if destination.is_symlink():
                        if not action.get("replace_symlink"):
                            raise PermissionError(
                                "copy_file refuses symlink target without replace_symlink"
                            )
                        destination.unlink()
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                elif kind == "delete":
                    remove_path(Path(action["path"]))
                elif kind == "command":
                    completed = subprocess.run(
                        action["argv"],
                        text=True,
                        capture_output=True,
                        timeout=int(action["timeout"]),
                        check=False,
                        shell=False,
                    )
                    result.update(
                        {
                            "returncode": completed.returncode,
                            "stdout": completed.stdout[-4000:],
                            "stderr": completed.stderr[-4000:],
                        }
                    )
                    if completed.returncode != 0:
                        raise RuntimeError(
                            f"command failed with return code {completed.returncode}"
                        )
                result["status"] = "completed"
        except Exception as exc:
            result.update({"status": "failed", "error": str(exc)})
            report["success"] = False
            report["results"].append(result)
            if not args.continue_on_error:
                break
        else:
            report["results"].append(result)

    report["finished_at"] = now()
    dump(report, args.output)
    print(args.output)
    return 0 if report["success"] else 2


def verify(args: argparse.Namespace) -> int:
    plan = load(args.plan)
    validate_plan(plan)
    passed, results = run_checks(plan.get("verification", []))
    report = {
        "schema_version": "1.1",
        "plan_id": plan["plan_id"],
        "plan_digest": canonical_digest(plan),
        "verified_at": now(),
        "passed": passed,
        "results": results,
    }
    dump(report, args.output)
    print(args.output)
    return 0 if passed else 3


def completed_command_indices(
    plan: dict[str, Any], execution_report: dict[str, Any] | None
) -> set[int]:
    command_indices = {
        index
        for index, action in enumerate(plan.get("actions", []))
        if action.get("type") == "command"
    }
    if not command_indices:
        return set()
    if execution_report is None:
        raise PermissionError("rollback of command actions requires --execution-report")
    if execution_report.get("plan_id") != plan.get("plan_id"):
        raise PermissionError("execution report plan_id does not match plan")
    return {
        int(result.get("index"))
        for result in execution_report.get("results", [])
        if isinstance(result, dict)
        and result.get("status") == "completed"
        and int(result.get("index", -1)) in command_indices
    }


def rollback(args: argparse.Namespace) -> int:
    plan = load(args.plan)
    actions = validate_plan(plan)
    manifest = load(args.manifest)
    manifest_verification = validate_manifest(plan, manifest)
    if args.apply:
        check_approval(plan, args)
    execution_report = load(args.execution_report) if args.execution_report else None
    command_indices = completed_command_indices(plan, execution_report)

    report: dict[str, Any] = {
        "schema_version": "1.1",
        "plan_id": plan["plan_id"],
        "plan_digest": canonical_digest(plan),
        "rolled_back_at": now(),
        "apply": args.apply,
        "manifest": str(Path(args.manifest).resolve()),
        "manifest_verified": manifest_verification["verified"],
        "success": True,
        "results": [],
        "command_results": [],
    }

    for entry in reversed(manifest.get("entries", [])):
        source = Path(entry["source"])
        result: dict[str, Any] = {
            "source": str(source),
            "status": "planned" if not args.apply else "pending",
        }
        try:
            if args.apply:
                remove_path(source)
                if entry.get("existed"):
                    backup = Path(entry["backup"])
                    source.parent.mkdir(parents=True, exist_ok=True)
                    copy_snapshot(backup, source)
                    actual = snapshot_digest(source)
                    if actual != entry.get("source_digest"):
                        raise RuntimeError(
                            "restored object digest does not match backup source"
                        )
                elif path_exists(source):
                    raise RuntimeError("new target still exists after rollback")
                result["status"] = "restored"
        except Exception as exc:
            report["success"] = False
            result.update({"status": "failed", "error": str(exc)})
            report["results"].append(result)
            if not args.continue_on_error:
                break
        else:
            report["results"].append(result)

    if report["success"] or args.continue_on_error:
        for index in sorted(command_indices, reverse=True):
            action = actions[index]
            result: dict[str, Any] = {
                "index": index,
                "executable": action["rollback_argv"][0],
                "status": "planned" if not args.apply else "pending",
            }
            try:
                if args.apply:
                    completed = subprocess.run(
                        action["rollback_argv"],
                        text=True,
                        capture_output=True,
                        timeout=int(action["rollback_timeout"]),
                        check=False,
                        shell=False,
                    )
                    result.update(
                        {
                            "returncode": completed.returncode,
                            "stdout": completed.stdout[-4000:],
                            "stderr": completed.stderr[-4000:],
                        }
                    )
                    if completed.returncode != 0:
                        raise RuntimeError(
                            "rollback command failed with return code "
                            f"{completed.returncode}"
                        )
                    result["status"] = "completed"
            except Exception as exc:
                report["success"] = False
                result.update({"status": "failed", "error": str(exc)})
                report["command_results"].append(result)
                if not args.continue_on_error:
                    break
            else:
                report["command_results"].append(result)

    dump(report, args.output)
    print(args.output)
    return 0 if report["success"] else 4


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)

    item = sub.add_parser("plan")
    item.add_argument("--discovery", required=True)
    item.add_argument("--request", required=True)
    item.add_argument("--output", default="operation-plan.json")
    item.set_defaults(func=make_plan)

    item = sub.add_parser("backup")
    item.add_argument("--plan", required=True)
    item.add_argument("--backup-root", default=".aiops-backups")
    item.add_argument("--replace", action="store_true")
    item.set_defaults(func=make_backup)

    item = sub.add_parser("execute")
    item.add_argument("--plan", required=True)
    item.add_argument("--manifest")
    item.add_argument("--output", default="execution-report.json")
    item.add_argument("--apply", action="store_true")
    item.add_argument("--approved", action="store_true")
    item.add_argument("--manual-preconditions-confirmed", action="store_true")
    item.add_argument("--continue-on-error", action="store_true")
    item.set_defaults(func=execute)

    item = sub.add_parser("verify")
    item.add_argument("--plan", required=True)
    item.add_argument("--output", default="verification-report.json")
    item.set_defaults(func=verify)

    item = sub.add_parser("rollback")
    item.add_argument("--plan", required=True)
    item.add_argument("--manifest", required=True)
    item.add_argument("--execution-report")
    item.add_argument("--output", default="rollback-report.json")
    item.add_argument("--apply", action="store_true")
    item.add_argument("--approved", action="store_true")
    item.add_argument("--continue-on-error", action="store_true")
    item.set_defaults(func=rollback)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        return int(args.func(args))
    except (
        OSError,
        ValueError,
        KeyError,
        PermissionError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
