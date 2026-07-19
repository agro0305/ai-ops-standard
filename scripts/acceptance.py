#!/usr/bin/env python3
"""Run the complete non-destructive AI-OPS release acceptance suite."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def run_step(
    name: str,
    argv: list[str],
    *,
    cwd: Path,
    accepted_codes: set[int] | None = None,
    timeout: int = 600,
) -> dict[str, Any]:
    accepted_codes = accepted_codes or {0}
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
        returncode = completed.returncode
        stdout = completed.stdout[-8000:]
        stderr = completed.stderr[-8000:]
        error = None
    except (OSError, subprocess.SubprocessError) as exc:
        returncode = -1
        stdout = ""
        stderr = ""
        error = str(exc)
    return {
        "name": name,
        "argv": argv,
        "returncode": returncode,
        "accepted": returncode in accepted_codes,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout": stdout,
        "stderr": stderr,
        "error": error,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def operation_acceptance(project_root: Path, temporary: Path) -> list[dict[str, Any]]:
    python = sys.executable
    operations = project_root / "implementations/operations/aiops_operations.py"
    discovery = temporary / "discovery.json"
    request = temporary / "request.json"
    plan = temporary / "operation-plan.json"
    backup_root = temporary / "backups"
    target_dir = temporary / "target"
    target_file = target_dir / "status.txt"
    execution_dry = temporary / "execution-dry.json"
    execution = temporary / "execution.json"
    verification = temporary / "verification.json"
    rollback_preview = temporary / "rollback-preview.json"
    rollback = temporary / "rollback.json"

    write_json(discovery, {"host": {"hostname": "acceptance"}})
    write_json(
        request,
        {
            "plan_id": "acceptance-operation",
            "intent": "Exercise safe write and rollback in a temporary directory",
            "preconditions": [{"type": "writable", "path": str(temporary)}],
            "actions": [
                {"type": "mkdir", "path": str(target_dir)},
                {
                    "type": "write_file",
                    "path": str(target_file),
                    "content": "AI-OPS acceptance\n",
                },
            ],
            "verification": [
                {"type": "exists", "path": str(target_file)},
                {
                    "type": "file_contains",
                    "path": str(target_file),
                    "text": "AI-OPS acceptance",
                },
            ],
        },
    )

    steps: list[dict[str, Any]] = []
    steps.append(
        run_step(
            "operation-plan",
            [
                python,
                str(operations),
                "plan",
                "--discovery",
                str(discovery),
                "--request",
                str(request),
                "--output",
                str(plan),
            ],
            cwd=project_root,
        )
    )
    if not steps[-1]["accepted"]:
        return steps

    steps.append(
        run_step(
            "operation-backup",
            [
                python,
                str(operations),
                "backup",
                "--plan",
                str(plan),
                "--backup-root",
                str(backup_root),
            ],
            cwd=project_root,
        )
    )
    if not steps[-1]["accepted"]:
        return steps
    manifest = backup_root / "acceptance-operation" / "backup-manifest.json"

    steps.append(
        run_step(
            "operation-execute-dry-run",
            [
                python,
                str(operations),
                "execute",
                "--plan",
                str(plan),
                "--output",
                str(execution_dry),
            ],
            cwd=project_root,
        )
    )
    if target_file.exists():
        steps[-1]["accepted"] = False
        steps[-1]["error"] = "dry-run created the target file"
        return steps

    steps.append(
        run_step(
            "operation-execute-apply",
            [
                python,
                str(operations),
                "execute",
                "--plan",
                str(plan),
                "--manifest",
                str(manifest),
                "--apply",
                "--output",
                str(execution),
            ],
            cwd=project_root,
        )
    )
    if not steps[-1]["accepted"] or not target_file.is_file():
        if not target_file.is_file():
            steps[-1]["accepted"] = False
            steps[-1]["error"] = "apply did not create the target file"
        return steps

    steps.append(
        run_step(
            "operation-verify",
            [
                python,
                str(operations),
                "verify",
                "--plan",
                str(plan),
                "--output",
                str(verification),
            ],
            cwd=project_root,
        )
    )

    steps.append(
        run_step(
            "operation-rollback-preview",
            [
                python,
                str(operations),
                "rollback",
                "--plan",
                str(plan),
                "--manifest",
                str(manifest),
                "--output",
                str(rollback_preview),
            ],
            cwd=project_root,
        )
    )
    if not target_file.exists():
        steps[-1]["accepted"] = False
        steps[-1]["error"] = "rollback preview changed the target"
        return steps

    steps.append(
        run_step(
            "operation-rollback-apply",
            [
                python,
                str(operations),
                "rollback",
                "--plan",
                str(plan),
                "--manifest",
                str(manifest),
                "--apply",
                "--output",
                str(rollback),
            ],
            cwd=project_root,
        )
    )
    if target_dir.exists():
        steps[-1]["accepted"] = False
        steps[-1]["error"] = "rollback did not remove the newly created target directory"
    return steps


def incident_acceptance(project_root: Path, temporary: Path) -> list[dict[str, Any]]:
    python = sys.executable
    incidents = project_root / "implementations/incidents/aiops_incidents.py"
    compliance = temporary / "compliance-result.json"
    write_json(
        compliance,
        {
            "generated_at": "2026-07-19T00:00:00+00:00",
            "summary": {"passed": 1, "failed": 1},
            "results": [],
        },
    )
    steps = [
        run_step(
            "incident-open",
            [
                python,
                str(incidents),
                "--root",
                str(temporary),
                "sync",
                "--actor",
                "acceptance",
                "--apply",
            ],
            cwd=project_root,
        )
    ]
    if not steps[-1]["accepted"]:
        return steps

    state_path = temporary / ".aiops-incidents/state.json.private"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    alert_ids = list(state.get("incidents", {}))
    if len(alert_ids) != 1:
        steps[-1]["accepted"] = False
        steps[-1]["error"] = f"expected one incident, found {len(alert_ids)}"
        return steps
    alert_id = alert_ids[0]

    steps.append(
        run_step(
            "incident-acknowledge",
            [
                python,
                str(incidents),
                "--root",
                str(temporary),
                "acknowledge",
                alert_id,
                "--actor",
                "acceptance",
                "--note",
                "Acceptance acknowledgement",
                "--apply",
            ],
            cwd=project_root,
        )
    )
    write_json(
        compliance,
        {
            "generated_at": "2026-07-19T00:05:00+00:00",
            "summary": {"passed": 2, "failed": 0},
            "results": [],
        },
    )
    steps.append(
        run_step(
            "incident-auto-resolve",
            [
                python,
                str(incidents),
                "--root",
                str(temporary),
                "sync",
                "--actor",
                "acceptance",
                "--apply",
            ],
            cwd=project_root,
        )
    )
    status = json.loads(
        (temporary / "incident-status.json").read_text(encoding="utf-8")
    )
    if status.get("summary", {}).get("resolved") != 1:
        steps[-1]["accepted"] = False
        steps[-1]["error"] = "incident was not automatically resolved"
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output", default="acceptance-result.json")
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    if not (project_root / "VERSION").is_file():
        parser.error(f"not an AI-OPS repository: {project_root}")
    version = (project_root / "VERSION").read_text(encoding="utf-8").strip()
    if not SEMVER.fullmatch(version):
        parser.error(f"invalid VERSION value: {version!r}")

    python = sys.executable
    started = time.monotonic()
    steps: list[dict[str, Any]] = []
    steps.append(
        run_step(
            "repository-validator",
            [python, "scripts/validate_repository.py"],
            cwd=project_root,
        )
    )
    steps.append(
        run_step(
            "compileall",
            [
                python,
                "-m",
                "compileall",
                "-q",
                "implementations",
                "scripts",
                "compliance/tests",
                "dashboard",
            ],
            cwd=project_root,
        )
    )
    installers = sorted((project_root / "dashboard").glob("install_*.sh"))
    for installer in installers:
        steps.append(
            run_step(
                f"shell-{installer.name}",
                ["bash", "-n", str(installer)],
                cwd=project_root,
            )
        )
    if not args.skip_pytest:
        steps.append(
            run_step(
                "pytest",
                [python, "-m", "pytest", "-q", "compliance/tests"],
                cwd=project_root,
                timeout=900,
            )
        )

    with tempfile.TemporaryDirectory(prefix="aiops-acceptance-") as temporary_name:
        temporary = Path(temporary_name)
        steps.extend(operation_acceptance(project_root, temporary / "operations"))
        incident_root = temporary / "incidents"
        incident_root.mkdir(parents=True)
        steps.extend(incident_acceptance(project_root, incident_root))

    success = all(step["accepted"] for step in steps)
    report = {
        "schema_version": "1.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "project_root": str(project_root),
        "version": version,
        "success": success,
        "duration_seconds": round(time.monotonic() - started, 3),
        "steps": steps,
    }
    output = Path(args.output).expanduser().resolve()
    write_json(output, report)
    print(output)
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
