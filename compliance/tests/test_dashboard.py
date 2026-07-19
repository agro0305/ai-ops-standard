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
