#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import errno
import hmac
import ipaddress
import json
import os
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlsplit

DASHBOARD_DIR = Path(__file__).resolve().parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from report_store import ReportStore  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    data_dir = Path(".")
    static_dir = DASHBOARD_DIR / "static"
    store = ReportStore(".")
    auth_token: str | None = None

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
        )

    def _send_bytes(
        self,
        body: bytes,
        content_type: str,
        *,
        status: int = 200,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(
            body,
            "application/json; charset=utf-8",
            status=status,
        )

    def _authorized(self) -> bool:
        return request_is_authorized(self.headers, self.auth_token)

    def _send_unauthorized(self) -> None:
        body = b"Authentication required."
        self.send_response(401)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "WWW-Authenticate",
            'Basic realm="AI-OPS Dashboard", charset="UTF-8"',
        )
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, filename: str) -> None:
        allowed = {
            "index.html": "text/html; charset=utf-8",
            "app.js": "application/javascript; charset=utf-8",
            "style.css": "text/css; charset=utf-8",
        }
        content_type = allowed.get(filename)
        if content_type is None:
            self._send_json({"error": "not found"}, status=404)
            return
        path = (self.static_dir / filename).resolve()
        try:
            path.relative_to(self.static_dir.resolve())
            body = path.read_bytes()
        except (OSError, ValueError):
            self._send_json({"error": "not found"}, status=404)
            return
        self._send_bytes(body, content_type)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path

        if path == "/healthz":
            self._send_json({"status": "ok"})
            return

        if path == "/readyz":
            ready = self.store.ready()
            self._send_json(
                {"status": "ready" if ready else "not-ready"},
                status=200 if ready else 503,
            )
            return

        if not self._authorized():
            self._send_unauthorized()
            return

        if path == "/":
            self._serve_static("index.html")
            return
        if path == "/static/app.js":
            self._serve_static("app.js")
            return
        if path == "/static/style.css":
            self._serve_static("style.css")
            return

        if path == "/api/summary":
            self._send_json(self.store.summary())
            return

        if path == "/api/reports":
            self._send_json(self.store.list_reports())
            return

        prefix = "/api/reports/"
        if path.startswith(prefix):
            name = unquote(path[len(prefix):])
            try:
                report = self.store.get_report(name)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except FileNotFoundError:
                self._send_json({"error": "report not found"}, status=404)
                return
            status = 422 if report.get("error") else 200
            self._send_json(report, status=status)
            return

        self._send_json({"error": "not found"}, status=404)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.client_address[0]} - {fmt % args}", file=sys.stderr)


def _basic_password(authorization: str) -> str:
    if not authorization.startswith("Basic "):
        return ""
    encoded = authorization[6:].strip()
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return ""
    if ":" not in decoded:
        return ""
    username, password = decoded.split(":", 1)
    if username != "aiops":
        return ""
    return password


def request_is_authorized(headers: Mapping[str, str], token: str | None) -> bool:
    """Validate Basic, Bearer or X-AI-OPS-Token credentials."""
    if token is None:
        return True

    authorization = headers.get("Authorization", "")
    supplied = ""
    if authorization.startswith("Bearer "):
        supplied = authorization[7:].strip()
    elif authorization.startswith("Basic "):
        supplied = _basic_password(authorization)
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
            raise ValueError(
                f"cannot read authentication token file {path}: {exc}"
            ) from exc
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
    raise OSError(
        last_error.errno if last_error else errno.EADDRINUSE,
        message,
    )


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
        "docker",
        "br-",
        "veth",
        "virbr",
        "cni",
        "flannel",
        "cali",
        "tunl",
        "kube-ipvs",
        "podman",
        "lxcbr",
    )
    return lowered.startswith(prefixes)


def _run_ip_json(arguments: list[str]) -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["ip", "-j", *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
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
        if (
            not is_default
            and not is_tailscale
            and is_virtual_interface(interface_name)
        ):
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
            for item in socket.getaddrinfo(
                socket.gethostname(),
                None,
                socket.AF_INET,
            ):
                address = str(item[4][0])
                label = classify_address(address)
                if label and label != "Local":
                    addresses.add((label, address))
        except OSError:
            pass

    priority = {"Local": 0, "LAN": 1, "Tailscale": 2, "Network": 3}
    return sorted(
        addresses,
        key=lambda item: (
            priority[item[0]],
            ipaddress.ip_address(item[1]),
        ),
    )


def advertised_urls(bind_host: str, port: int) -> list[tuple[str, str]]:
    if bind_host not in {"0.0.0.0", "::", ""}:
        label = classify_address(bind_host) or "Dashboard"
        return [(label, f"http://{bind_host}:{port}")]
    return [
        (label, f"http://{address}:{port}")
        for label, address in discover_ipv4_addresses()
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=".")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--auth-token-file")
    parser.add_argument(
        "--strict-port",
        action="store_true",
        help="Fail instead of selecting the next available port.",
    )
    parser.add_argument("--max-port-attempts", type=int, default=100)
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    static_dir = DASHBOARD_DIR / "static"
    if not data_dir.is_dir():
        parser.error(f"data directory does not exist: {data_dir}")
    if not static_dir.is_dir():
        parser.error(f"dashboard static directory does not exist: {static_dir}")
    if args.max_port_attempts < 0:
        parser.error("--max-port-attempts must be zero or greater")

    try:
        Handler.auth_token = load_auth_token(args.auth_token_file)
    except ValueError as exc:
        parser.error(str(exc))
    Handler.data_dir = data_dir
    Handler.static_dir = static_dir.resolve()
    Handler.store = ReportStore(data_dir)

    try:
        server, selected_port = create_server(
            args.host,
            args.port,
            strict_port=args.strict_port,
            max_port_attempts=args.max_port_attempts,
        )
    except (OSError, ValueError) as exc:
        print(f"Dashboard startup failed: {exc}", file=sys.stderr)
        return 1

    if selected_port != args.port and args.port != 0:
        print(
            f"Port {args.port} is occupied or unavailable; "
            f"using port {selected_port} instead.",
            file=sys.stderr,
        )

    print(f"Listening on {args.host}:{selected_port}")
    for label, url in advertised_urls(args.host, selected_port):
        print(f"{label}: {url}")
    print(f"Authentication: {'enabled' if Handler.auth_token else 'disabled'}")
    if args.host in {"0.0.0.0", "::", ""} and not Handler.auth_token:
        print(
            "Warning: dashboard is exposed on all interfaces "
            "and has no authentication."
        )
    elif args.host in {"0.0.0.0", "::", ""}:
        print("Browser login username: aiops")
        print(
            "Warning: authentication is enabled, "
            "but HTTP traffic is not encrypted."
        )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
