#!/usr/bin/env python3
from __future__ import annotations

import argparse
import errno
import hmac
import html
import ipaddress
import json
import os
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping


class Handler(BaseHTTPRequestHandler):
    data_dir = Path(".")
    auth_token: str | None = None

    def _send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        return request_is_authorized(self.headers, self.auth_token)

    def _send_unauthorized(self) -> None:
        body = b"Authentication required."
        self.send_response(401)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("WWW-Authenticate", 'Bearer realm="AI-OPS Dashboard"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send_json({"status": "ok", "data_dir": str(self.data_dir)})
            return

        if not self._authorized():
            self._send_unauthorized()
            return

        if self.path == "/api/reports":
            items = []
            for path in sorted(self.data_dir.glob("*.json")):
                try:
                    items.append(
                        {
                            "name": path.name,
                            "data": json.loads(path.read_text(encoding="utf-8")),
                        }
                    )
                except Exception as exc:
                    items.append({"name": path.name, "error": str(exc)})
            self._send_json(items)
            return

        if self.path != "/":
            self._send_json({"error": "not found"}, status=404)
            return

        rows = []
        for path in sorted(self.data_dir.glob("*.json")):
            rows.append(
                f"<tr><td>{html.escape(path.name)}</td><td>{path.stat().st_size}</td></tr>"
            )
        page = f"""<!doctype html><html><head><meta charset='utf-8'><title>AI-OPS Dashboard</title>
<style>body{{font-family:system-ui;margin:2rem;background:#111;color:#eee}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #555;padding:.6rem;text-align:left}}code{{color:#9fe}}</style></head>
<body><h1>AI-OPS Dashboard</h1><p>Read-only local report index.</p><table><tr><th>Report</th><th>Bytes</th></tr>{''.join(rows)}</table><p>JSON API: <code>/api/reports</code> · Health: <code>/healthz</code></p></body></html>""".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.client_address[0]} - {fmt % args}", file=sys.stderr)


def request_is_authorized(headers: Mapping[str, str], token: str | None) -> bool:
    """Validate Bearer or X-AI-OPS-Token credentials without leaking values."""
    if token is None:
        return True

    authorization = headers.get("Authorization", "")
    supplied = ""
    if authorization.startswith("Bearer "):
        supplied = authorization[7:].strip()
    if not supplied:
        supplied = headers.get("X-AI-OPS-Token", "").strip()
    return bool(supplied) and hmac.compare_digest(supplied, token)


def load_auth_token(token_file: str | None) -> str | None:
    """Load authentication from a file or AIOPS_DASHBOARD_TOKEN."""
    if token_file:
        path = Path(token_file).expanduser().resolve()
        try:
            token = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(f"cannot read authentication token file {path}: {exc}") from exc
        if not token:
            raise ValueError(f"authentication token file is empty: {path}")
        return token

    token = os.environ.get("AIOPS_DASHBOARD_TOKEN", "").strip()
    return token or None


def create_server(
    host: str,
    requested_port: int,
    *,
    strict_port: bool = False,
    max_port_attempts: int = 100,
) -> tuple[ThreadingHTTPServer, int]:
    """Bind the requested port or the next available port without a race."""
    if not 0 <= requested_port <= 65535:
        raise ValueError("port must be between 0 and 65535")

    ports = [requested_port]
    if not strict_port and requested_port != 0:
        last_port = min(65535, requested_port + max_port_attempts)
        ports.extend(range(requested_port + 1, last_port + 1))

    last_error: OSError | None = None
    for port in ports:
        try:
            server = ThreadingHTTPServer((host, port), Handler)
            return server, int(server.server_address[1])
        except OSError as exc:
            last_error = exc
            if exc.errno not in {errno.EADDRINUSE, errno.EACCES} or strict_port:
                raise

    message = (
        f"No available port found from {requested_port} "
        f"through {ports[-1] if ports else requested_port}."
    )
    raise OSError(last_error.errno if last_error else errno.EADDRINUSE, message)


def classify_address(address: str) -> str | None:
    """Return a user-facing network label for an IPv4 address."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return None

    if ip.version != 4 or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
        return None
    if ip.is_loopback:
        return "Local"
    if ip in ipaddress.ip_network("100.64.0.0/10"):
        return "Tailscale"
    if ip.is_private:
        return "LAN"
    return "Network"


def is_virtual_interface(name: str) -> bool:
    lowered = name.lower()
    prefixes = (
        "docker", "br-", "veth", "virbr", "cni", "flannel", "cali",
        "tunl", "kube-ipvs", "podman", "lxcbr",
    )
    return lowered.startswith(prefixes)


def _run_ip_json(arguments: list[str]) -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["ip", "-j", *arguments], check=False, capture_output=True,
            text=True, timeout=3,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def discover_default_interfaces() -> set[str]:
    interfaces: set[str] = set()
    for route in _run_ip_json(["-4", "route", "show", "default"]):
        device = route.get("dev")
        if device:
            interfaces.add(str(device))
    return interfaces


def discover_ipv4_addresses() -> list[tuple[str, str]]:
    """Discover browser-relevant Local, LAN and Tailscale addresses."""
    addresses: set[tuple[str, str]] = {("Local", "127.0.0.1")}
    default_interfaces = discover_default_interfaces()
    found_non_loopback = False

    for interface in _run_ip_json(["-4", "addr", "show", "up"]):
        interface_name = str(interface.get("ifname") or "")
        if not interface_name or interface_name == "lo":
            continue
        is_default = interface_name in default_interfaces
        is_tailscale = interface_name.lower().startswith("tailscale")
        if not is_default and not is_tailscale and is_virtual_interface(interface_name):
            continue
        if default_interfaces and not is_default and not is_tailscale:
            continue
        for item in interface.get("addr_info", []):
            if item.get("family") != "inet" or not item.get("local"):
                continue
            address = str(item["local"])
            label = classify_address(address)
            if label and label != "Local":
                addresses.add((label, address))
                found_non_loopback = True

    if not found_non_loopback:
        try:
            for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                address = str(item[4][0])
                label = classify_address(address)
                if label and label != "Local":
                    addresses.add((label, address))
        except OSError:
            pass

    priority = {"Local": 0, "LAN": 1, "Tailscale": 2, "Network": 3}
    return sorted(addresses, key=lambda item: (priority[item[0]], ipaddress.ip_address(item[1])))


def advertised_urls(bind_host: str, port: int) -> list[tuple[str, str]]:
    if bind_host not in {"0.0.0.0", "::", ""}:
        label = classify_address(bind_host) or "Dashboard"
        return [(label, f"http://{bind_host}:{port}")]
    return [(label, f"http://{address}:{port}") for label, address in discover_ipv4_addresses()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=".")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--auth-token-file")
    parser.add_argument("--strict-port", action="store_true", help="Fail instead of selecting the next available port.")
    parser.add_argument("--max-port-attempts", type=int, default=100)
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    if not data_dir.is_dir():
        parser.error(f"data directory does not exist: {data_dir}")
    if args.max_port_attempts < 0:
        parser.error("--max-port-attempts must be zero or greater")

    try:
        Handler.auth_token = load_auth_token(args.auth_token_file)
    except ValueError as exc:
        parser.error(str(exc))
    Handler.data_dir = data_dir

    try:
        server, selected_port = create_server(
            args.host, args.port, strict_port=args.strict_port,
            max_port_attempts=args.max_port_attempts,
        )
    except (OSError, ValueError) as exc:
        print(f"Dashboard startup failed: {exc}", file=sys.stderr)
        return 1

    if selected_port != args.port and args.port != 0:
        print(f"Port {args.port} is occupied or unavailable; using port {selected_port} instead.", file=sys.stderr)

    print(f"Listening on {args.host}:{selected_port}")
    for label, url in advertised_urls(args.host, selected_port):
        print(f"{label}: {url}")
    print(f"Authentication: {'enabled' if Handler.auth_token else 'disabled'}")
    if args.host in {"0.0.0.0", "::", ""} and not Handler.auth_token:
        print("Warning: dashboard is exposed on all interfaces and has no authentication.")
    elif args.host in {"0.0.0.0", "::", ""}:
        print("Warning: Bearer authentication is enabled, but HTTP traffic is not encrypted.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
