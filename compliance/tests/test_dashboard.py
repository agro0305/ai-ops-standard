from __future__ import annotations

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
            "127.0.0.1",
            occupied_port,
            max_port_attempts=20,
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
            MODULE.create_server(
                "127.0.0.1",
                occupied_port,
                strict_port=True,
            )
        except OSError:
            pass
        else:
            raise AssertionError("strict port mode must fail for an occupied port")
    finally:
        occupied_socket.close()


def test_dashboard_classifies_common_addresses():
    assert MODULE.classify_address("127.0.0.1") == "Local"
    assert MODULE.classify_address("192.168.0.110") == "LAN"
    assert MODULE.classify_address("10.0.0.5") == "LAN"
    assert MODULE.classify_address("100.64.10.20") == "Tailscale"
    assert MODULE.classify_address("8.8.8.8") == "Network"
    assert MODULE.classify_address("169.254.1.1") is None
    assert MODULE.classify_address("not-an-ip") is None


def test_dashboard_advertises_explicit_host_only():
    assert MODULE.advertised_urls("192.168.0.110", 8789) == [
        ("LAN", "http://192.168.0.110:8789")
    ]


def test_dashboard_advertises_discovered_addresses_for_wildcard(monkeypatch):
    monkeypatch.setattr(
        MODULE,
        "discover_ipv4_addresses",
        lambda: [
            ("Local", "127.0.0.1"),
            ("LAN", "192.168.0.110"),
            ("Tailscale", "100.64.10.20"),
        ],
    )
    assert MODULE.advertised_urls("0.0.0.0", 8789) == [
        ("Local", "http://127.0.0.1:8789"),
        ("LAN", "http://192.168.0.110:8789"),
        ("Tailscale", "http://100.64.10.20:8789"),
    ]
