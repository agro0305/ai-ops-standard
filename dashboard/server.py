#!/usr/bin/env python3
from __future__ import annotations

import argparse
import errno
import html
import ipaddress
import json
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    data_dir = Path(".")

    def _send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send_json({"status": "ok", "data_dir": str(self.data_dir)})
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
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.client_address[0]} - {fmt % args}", file=sys.stderr)


def create_server(
    host: str,
    requested_port: int,
    *,
    strict_port: bool = False,
    max_port_attempts: int = 100,
) -> tuple[ThreadingHTTPServer, int]:
    """Bind the requested port or the next available port.

    The server object itself performs the bind, avoiding a check-then-bind race.
    """
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


def discover_ipv4_addresses() -> list[tuple[str, str]]:
    """Discover usable IPv4 addresses without failing dashboard startup."""
    addresses: set[str] = {"127.0.0.1"}

    try:
        result = subprocess.run(
            ["ip", "-j", "-4", "addr", "show", "up"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            for interface in json.loads(result.stdout or "[]"):
                for item in interface.get("addr_info", []):
                    if item.get("family") == "inet" and item.get("local"):
                        addresses.add(str(item["local"]))
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(str(item[4][0]))
    except OSError:
        pass

    classified = []
    priority = {"Local": 0, "LAN": 1, "Tailscale": 2, "Network": 3}
    for address in addresses:
        label = classify_address(address)
        if label:
            classified.append((label, address))
    return sorted(classified, key=lambda item: (priority[item[0]], ipaddress.ip_address(item[1])))


def advertised_urls(bind_host: str, port: int) -> list[tuple[str, str]]:
    """Build addresses that users can actually open in a browser."""
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
    parser.add_argument(
        "--strict-port",
        action="store_true",
        help="Fail instead of selecting the next available port.",
    )
    parser.add_argument(
        "--max-port-attempts",
        type=int,
        default=100,
        help="Maximum number of following ports to try when the requested port is occupied.",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    if not data_dir.is_dir():
        parser.error(f"data directory does not exist: {data_dir}")
    if args.max_port_attempts < 0:
        parser.error("--max-port-attempts must be zero or greater")

    Handler.data_dir = data_dir

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
            f"Port {args.port} is occupied or unavailable; using port {selected_port} instead.",
            file=sys.stderr,
        )

    print(f"Listening on {args.host}:{selected_port}")
    for label, url in advertised_urls(args.host, selected_port):
        print(f"{label}: {url}")
    if args.host in {"0.0.0.0", "::", ""}:
        print("Warning: dashboard is exposed on all interfaces and has no authentication.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
