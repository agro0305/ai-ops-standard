from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "runtime_health.py"
SPEC = importlib.util.spec_from_file_location("aiops_runtime_health_http", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, _limit: int) -> bytes:
        return json.dumps({"status": "ok"}).encode("utf-8")


def test_check_http_records_http_status_without_overwriting_check_status(monkeypatch):
    monkeypatch.setattr(MODULE.urllib.request, "urlopen", lambda request, timeout: FakeResponse())

    check = MODULE.check_http("http://127.0.0.1:8789/healthz", required=True)

    assert check["status"] == "pass"
    assert check["http_status"] == 200
    assert check["payload"] == {"status": "ok"}
