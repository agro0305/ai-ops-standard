from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "refresh_reports.py"
SPEC = importlib.util.spec_from_file_location("aiops_refresh_reports", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_script(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def make_project(root: Path, *, inventory_exit: int = 0) -> None:
    write_script(
        root / "implementations/discovery/aiops_discovery.py",
        """import argparse, json
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--output', required=True); a=p.parse_args()
Path(a.output).write_text(json.dumps({'report_id':'x','generated_at':'now','collectors':{},'errors':[]}), encoding='utf-8')
""",
    )
    write_script(
        root / "implementations/inventory/aiops_inventory.py",
        f"""import argparse, json, sys
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--output', required=True); a=p.parse_args()
Path(a.output).write_text(json.dumps({{'agents':[],'mcp':{{'config_candidates':[]}},'permissions':{{}}}}), encoding='utf-8')
sys.exit({inventory_exit})
""",
    )
    write_script(
        root / "implementations/compliance/aiops_compliance.py",
        """import argparse, json, sys
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--discovery'); p.add_argument('--registry'); p.add_argument('--output', required=True); a=p.parse_args()
Path(a.output).write_text(json.dumps({'summary':{'passed':3,'failed':1},'results':[]}), encoding='utf-8')
sys.exit(1)
""",
    )


def test_refresh_accepts_compliance_failure_status_and_commits_all_reports(tmp_path):
    project = tmp_path / "project"
    output = tmp_path / "output"
    make_project(project)

    code, status = MODULE.run_refresh(project, output, python_executable=sys.executable)

    assert code == 0
    assert status["success"] is True
    assert (output / "discovery-report.json").is_file()
    assert (output / "ai-capability-registry.json").is_file()
    assert (output / "compliance-result.json").is_file()
    assert json.loads((output / "compliance-result.json").read_text())["summary"]["failed"] == 1


def test_refresh_is_all_or_nothing_when_inventory_fails(tmp_path):
    project = tmp_path / "project"
    output = tmp_path / "output"
    output.mkdir()
    make_project(project, inventory_exit=2)
    original = {"old": True}
    (output / "discovery-report.json").write_text(json.dumps(original), encoding="utf-8")

    code, status = MODULE.run_refresh(project, output, python_executable=sys.executable)

    assert code == 2
    assert status["success"] is False
    assert json.loads((output / "discovery-report.json").read_text()) == original
    assert not (output / "ai-capability-registry.json").exists()
    assert not (output / "compliance-result.json").exists()


def test_atomic_status_writer_replaces_existing_file(tmp_path):
    path = tmp_path / "refresh-status.json"
    path.write_text("old", encoding="utf-8")
    MODULE.write_json_atomic(path, {"success": True})
    assert json.loads(path.read_text(encoding="utf-8")) == {"success": True}
