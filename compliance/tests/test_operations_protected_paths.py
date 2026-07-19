from __future__ import annotations

import importlib.util
import json
from argparse import Namespace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "implementations" / "operations" / "aiops_operations.py"
SPEC = importlib.util.spec_from_file_location("aiops_operations_protected", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_exact_system_roots_are_never_valid_targets(tmp_path):
    discovery = tmp_path / "discovery.json"
    discovery.write_text(json.dumps({"host": {}}), encoding="utf-8")
    for index, target in enumerate(sorted(MODULE.PROTECTED_EXACT_TARGETS)):
        request = tmp_path / f"request-{index}.json"
        request.write_text(
            json.dumps(
                {
                    "plan_id": f"protected-{index}",
                    "actions": [{"type": "delete", "path": target}],
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="protected system root"):
            MODULE.make_plan(
                Namespace(
                    discovery=str(discovery),
                    request=str(request),
                    output=str(tmp_path / f"plan-{index}.json"),
                )
            )


def test_subpath_can_be_planned_and_is_risk_classified(tmp_path):
    action = MODULE.normalize_action({"type": "write_file", "path": "/etc/aiops/example.conf"})
    assert action["path"] == "/etc/aiops/example.conf"
    assert MODULE.classify_risk([action]) == "high"
