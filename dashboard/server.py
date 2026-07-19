#!/usr/bin/env python3
from __future__ import annotations

import argparse
import errno
import html
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    data_dir = Path(".")

    def do_GET(self) -> None:
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
            body = json.dumps(items).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return

        rows = []
        for path in sorted(self.data_dir.glob("*.json")):
            rows.append(
                f"<tr><td>{html.escape(path.name)}</td><td>{path.stat().st_size}</td></tr>"
            )
        page = f"""<!doctype html><html><head><meta charset='utf-8'><title>AI-OPS Dashboard</title>
<style>body{{font-family:system-ui;margin:2rem;background:#111;color:#eee}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #555;padding:.6rem;text-align:left}}code{{color:#9fe}}</style></head>
<body><h1>AI-OPS Dashboard</h1><p>Read-only local report index.</p><table><tr><th>Report</th><th>Bytes</th></tr>{''.join(rows)}</table><p>JSON API: <code>/api/reports</code></p></body></html>""".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page)


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

    display_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    print(f"AI-OPS Dashboard: http://{display_host}:{selected_port}")
    print(f"Listening on {args.host}:{selected_port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
