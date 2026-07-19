from __future__ import annotations

import base64
import importlib.util
import socket
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "dashboard" / "server.py"
SPEC = importlib.util.spec_from_file_location("aiops_dashboard", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def occupy_port(host: str = "127.0.0.1") -> tuple[socket.socket, int]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, 0))
    sock.listen(1)
    return sock, int(sock.getsockname()[1])


def test_dashboard_uses_requested_free_port():
    server, port = MODULE.create_server("127.0.0.1", 0)
    try:
        assert port > 0
    finally:
        server.server_close()


def test_dashboard_selects_next_port_when_requested_port_is_occupied():
    occupied_socket, occupied_port = occupy_port()
    try:
        server, selected_port = MODULE.create_server(
            "127.0.0.1", occupied_port, max_port_attempts=20
        )
        try:
            assert selected_port != occupied_port
            assert selected_port > occupied_port
        finally:
            server.server_close()
    finally:
        occupied_socket.close()


def test_dashboard_strict_port_fails_when_port_is_occupied():
    occupied_socket, occupied_port = occupy_port()
    try:
        try:
            MODULE.create_server("127.0.0.1", occupied_port, strict_port=True)
        except OSError:
            pass
        else:
            raise AssertionError("strict port mode must fail for an occupied port")
    finally:
        occupied_socket.close()


def test_dashboard_classifies_common_addresses():
    assert MODULE.classify_address("127.0.0.1") == "Local"
    assert MODULE.classify_address("192.168.0.116") == "LAN"
    assert MODULE.classify_address("10.0.0.5") == "LAN"
    assert MODULE.classify_address("100.79.70.40") == "Tailscale"
    assert MODULE.classify_address("8.8.8.8") == "Network"
    assert MODULE.classify_address("169.254.1.1") is None
    assert MODULE.classify_address("not-an-ip") is None


def test_virtual_interface_detection():
    assert MODULE.is_virtual_interface("docker0")
    assert MODULE.is_virtual_interface("br-aabbcc")
    assert MODULE.is_virtual_interface("veth1234")
    assert not MODULE.is_virtual_interface("enp6s18")
    assert not MODULE.is_virtual_interface("tailscale0")


def test_dashboard_advertises_explicit_host_only():
    assert MODULE.advertised_urls("192.168.0.116", 8789) == [
        ("LAN", "http://192.168.0.116:8789")
    ]


def test_dashboard_advertises_discovered_addresses_for_wildcard(monkeypatch):
    monkeypatch.setattr(
        MODULE,
        "discover_ipv4_addresses",
        lambda: [
            ("Local", "127.0.0.1"),
            ("LAN", "192.168.0.116"),
            ("Tailscale", "100.79.70.40"),
        ],
    )
    assert MODULE.advertised_urls("0.0.0.0", 8789) == [
        ("Local", "http://127.0.0.1:8789"),
        ("LAN", "http://192.168.0.116:8789"),
        ("Tailscale", "http://100.79.70.40:8789"),
    ]


def test_dashboard_allows_requests_when_authentication_is_disabled():
    assert MODULE.request_is_authorized({}, None)


def test_dashboard_accepts_bearer_and_custom_header_tokens():
    token = "correct-secret"
    assert MODULE.request_is_authorized(
        {"Authorization": "Bearer correct-secret"}, token
    )
    assert MODULE.request_is_authorized(
        {"X-AI-OPS-Token": "correct-secret"}, token
    )


def test_dashboard_accepts_browser_basic_authentication():
    encoded = base64.b64encode(b"aiops:correct-secret").decode("ascii")
    assert MODULE.request_is_authorized(
        {"Authorization": f"Basic {encoded}"}, "correct-secret"
    )


def test_dashboard_rejects_wrong_basic_username_or_password():
    wrong_user = base64.b64encode(b"admin:correct-secret").decode("ascii")
    wrong_password = base64.b64encode(b"aiops:wrong-secret").decode("ascii")
    assert not MODULE.request_is_authorized(
        {"Authorization": f"Basic {wrong_user}"}, "correct-secret"
    )
    assert not MODULE.request_is_authorized(
        {"Authorization": f"Basic {wrong_password}"}, "correct-secret"
    )


def test_dashboard_rejects_missing_or_incorrect_tokens():
    token = "correct-secret"
    assert not MODULE.request_is_authorized({}, token)
    assert not MODULE.request_is_authorized(
        {"Authorization": "Bearer wrong-secret"}, token
    )


def test_dashboard_loads_token_file(tmp_path, monkeypatch):
    token_file = tmp_path / "dashboard.token"
    token_file.write_text("file-secret\n", encoding="utf-8")
    monkeypatch.setenv("AIOPS_DASHBOARD_TOKEN", "environment-secret")
    assert MODULE.load_auth_token(str(token_file)) == "file-secret"


def test_dashboard_loads_environment_token(monkeypatch):
    monkeypatch.setenv("AIOPS_DASHBOARD_TOKEN", "environment-secret")
    assert MODULE.load_auth_token(None) == "environment-secret"
