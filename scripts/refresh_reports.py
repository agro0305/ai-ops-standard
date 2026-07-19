#!/usr/bin/env python3
"""Refresh AI-OPS discovery, capability and compliance reports atomically."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_NAMES = (
    "discovery-report.json",
    "ai-capability-registry.json",
    "compliance-result.json",
)


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
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate_json(path: Path) -> None:
    with path.open("r", encoding="utf-8") as stream:
        json.load(stream)


def run_step(name: str, argv: list[str], accepted_codes: set[int]) -> dict[str, Any]:
    started = time.monotonic()
    result = subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    duration = round(time.monotonic() - started, 3)
    return {
        "name": name,
        "argv": argv,
        "returncode": result.returncode,
        "accepted": result.returncode in accepted_codes,
        "duration_seconds": duration,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def run_refresh(
    project_root: Path,
    output_dir: Path,
    *,
    python_executable: str = sys.executable,
) -> tuple[int, dict[str, Any]]:
    project_root = project_root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    discovery_script = project_root / "implementations/discovery/aiops_discovery.py"
    inventory_script = project_root / "implementations/inventory/aiops_inventory.py"
    compliance_script = project_root / "implementations/compliance/aiops_compliance.py"
    for script in (discovery_script, inventory_script, compliance_script):
        if not script.is_file():
            raise FileNotFoundError(f"missing required script: {script}")

    started_at = now()
    monotonic_start = time.monotonic()
    steps: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="aiops-refresh-", dir=output_dir) as tmp_name:
        temporary_dir = Path(tmp_name)
        discovery_tmp = temporary_dir / REPORT_NAMES[0]
        registry_tmp = temporary_dir / REPORT_NAMES[1]
        compliance_tmp = temporary_dir / REPORT_NAMES[2]

        steps.append(
            run_step(
                "discovery",
                [python_executable, str(discovery_script), "--output", str(discovery_tmp)],
                {0},
            )
        )
        if steps[-1]["accepted"]:
            steps.append(
                run_step(
                    "capability-registry",
                    [python_executable, str(inventory_script), "--output", str(registry_tmp)],
                    {0},
                )
            )
        if all(step["accepted"] for step in steps):
            steps.append(
                run_step(
                    "compliance",
                    [
                        python_executable,
                        str(compliance_script),
                        "--discovery",
                        str(discovery_tmp),
                        "--registry",
                        str(registry_tmp),
                        "--output",
                        str(compliance_tmp),
                    ],
                    {0, 1},
                )
            )

        success = len(steps) == 3 and all(step["accepted"] for step in steps)
        if success:
            try:
                for path in (discovery_tmp, registry_tmp, compliance_tmp):
                    validate_json(path)
            except (OSError, json.JSONDecodeError) as exc:
                steps.append(
                    {
                        "name": "validate-json",
                        "accepted": False,
                        "error": str(exc),
                    }
                )
                success = False

        if success:
            for source, name in zip(
                (discovery_tmp, registry_tmp, compliance_tmp), REPORT_NAMES
            ):
                destination = output_dir / name
                os.replace(source, destination)
                destination.chmod(0o640)

    status = {
        "schema_version": "1.0",
        "generated_at": now(),
        "started_at": started_at,
        "success": success,
        "duration_seconds": round(time.monotonic() - monotonic_start, 3),
        "project_root": str(project_root),
        "output_dir": str(output_dir),
        "reports": list(REPORT_NAMES) if success else [],
        "steps": steps,
    }
    write_json_atomic(output_dir / "refresh-status.json", status)
    return (0 if success else 2), status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parents[1]),
    )
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--lock-file")
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    lock_path = (
        Path(args.lock_file).expanduser().resolve()
        if args.lock_file
        else output_dir / ".aiops-refresh.lock"
    )
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("a+", encoding="utf-8") as lock_stream:
        try:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("AI-OPS report refresh is already running.")
            return 0

        try:
            code, status = run_refresh(project_root, output_dir)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            status = {
                "schema_version": "1.0",
                "generated_at": now(),
                "success": False,
                "project_root": str(project_root),
                "output_dir": str(output_dir),
                "error": str(exc),
            }
            write_json_atomic(output_dir / "refresh-status.json", status)
            print(f"Refresh failed: {exc}", file=sys.stderr)
            return 2

    print(output_dir / "refresh-status.json")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
