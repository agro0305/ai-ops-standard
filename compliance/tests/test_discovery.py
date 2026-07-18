from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "implementations" / "discovery" / "aiops_discovery.py"


def load_module():
    spec = importlib.util.spec_from_file_location("aiops_discovery", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_redaction_hides_common_secrets():
    module = load_module()
    text = "token=abc123 password: swordfish Authorization: Bearer hidden"
    redacted = module.redact(text)
    assert "abc123" not in redacted
    assert "swordfish" not in redacted
    assert "hidden" not in redacted
    assert redacted.count("[REDACTED]") == 3


def test_cli_lists_collectors():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--list-collectors"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    names = set(result.stdout.split())
    assert {"system", "network", "services", "containers", "development", "ai", "platform"} <= names


def test_cli_generates_minimal_json(tmp_path: Path):
    output = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--collect",
            "development",
            "--compact",
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["mode"] == "read_only"
    assert report["generator"]["name"] == "aiops-discovery"
    assert set(report["collectors"]) == {"development"}
    assert isinstance(report["errors"], list)


def test_unknown_collector_fails():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--collect", "unknown"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Unknown collectors" in result.stderr
