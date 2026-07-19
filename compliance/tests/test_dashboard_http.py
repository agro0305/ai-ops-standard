from __future__ import annotations

import base64
import importlib.util
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "dashboard" / "server.py"
SPEC = importlib.util.spec_from_file_location("aiops_dashboard_http", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def request(url: str, token: str | None = None):
    headers = {}
    if token is not None:
        encoded = base64.b64encode(f"aiops:{token}".encode()).decode("ascii")
        headers["Authorization"] = f"Basic {encoded}"
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=headers),
        timeout=3,
    )


def start_server(tmp_path: Path, token: str = "test-secret"):
    (tmp_path / "discovery-report.json").write_text(
        json.dumps(
            {
                "report_id": "r1",
                "collectors": {"system": {}},
                "errors": [],
                "effective_user": {"name": "tester"},
            }
        ),
        encoding="utf-8",
    )
    MODULE.Handler.data_dir = tmp_path
    MODULE.Handler.static_dir = MODULE.DASHBOARD_DIR / "static"
    MODULE.Handler.store = MODULE.ReportStore(tmp_path)
    MODULE.Handler.auth_token = token
    server, port = MODULE.create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{port}", token


def stop_server(server, thread):
    server.shutdown()
    thread.join(timeout=3)
    server.server_close()


def test_health_is_public_but_dashboard_requires_authentication(tmp_path):
    server, thread, base_url, token = start_server(tmp_path)
    try:
        with request(f"{base_url}/healthz") as response:
            assert json.load(response) == {"status": "ok"}
        try:
            request(f"{base_url}/")
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("dashboard must require authentication")
        with request(f"{base_url}/", token) as response:
            assert b"Operativni pregled" in response.read()
    finally:
        stop_server(server, thread)


def test_dashboard_summary_and_report_detail_api(tmp_path):
    server, thread, base_url, token = start_server(tmp_path)
    try:
        with request(f"{base_url}/api/summary", token) as response:
            summary = json.load(response)
        assert summary["report_count"] == 1

        name = urllib.parse.quote("discovery-report.json", safe="")
        with request(f"{base_url}/api/reports/{name}", token) as response:
            report = json.load(response)
        assert report["category"] == "discovery"
        assert report["data"]["report_id"] == "r1"
    finally:
        stop_server(server, thread)


def test_dashboard_report_api_rejects_path_traversal(tmp_path):
    server, thread, base_url, token = start_server(tmp_path)
    try:
        traversal = urllib.parse.quote("../secret.json", safe="")
        try:
            request(f"{base_url}/api/reports/{traversal}", token)
        except urllib.error.HTTPError as exc:
            assert exc.code in {400, 404}
        else:
            raise AssertionError("path traversal request must fail")
    finally:
        stop_server(server, thread)
