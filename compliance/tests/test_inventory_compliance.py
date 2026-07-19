import importlib.util, json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_inventory_cli(tmp_path):
    out=tmp_path/"registry.json"
    subprocess.run([sys.executable,str(ROOT/"implementations/inventory/aiops_inventory.py"),"--output",str(out)],check=True)
    data=json.loads(out.read_text())
    assert isinstance(data["agents"],list)
    assert "mcp" in data and "permissions" in data

def test_compliance_runner(tmp_path):
    reg=tmp_path/"registry.json"; result=tmp_path/"result.json"
    reg.write_text(json.dumps({"agents":[],"mcp":{"config_candidates":[]},"permissions":{}}))
    proc=subprocess.run([sys.executable,str(ROOT/"implementations/compliance/aiops_compliance.py"),"--registry",str(reg),"--output",str(result)])
    data=json.loads(result.read_text())
    assert data["summary"]["passed"]>=3
    assert proc.returncode in (0,1)
