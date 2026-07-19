#!/usr/bin/env python3
"""AI-OPS AIS-0003 read-only discovery reference implementation."""

from __future__ import annotations

import argparse
import json
import os
import platform
import pwd
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

VERSION = "0.1.1"
DEFAULT_TIMEOUT = 8
DEFAULT_VERSION_TIMEOUT = 5
DEFAULT_VERSION_WORKERS = 8

SECRET_PATTERNS = [
    re.compile(r"(?i)(authorization:\s*(?:bearer|basic)\s+)[^\s]+"),
    re.compile(r"(?i)((?:api[_-]?key|token|secret|password)\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
]


def redact(value: str) -> str:
    result = value
    for pattern in SECRET_PATTERNS:
        result = pattern.sub(lambda m: (m.group(1) if m.lastindex else "") + "[REDACTED]", result)
    return result


def candidate_homes() -> list[Path]:
    """Return real user homes that may contain CLI installations.

    Discovery is often launched by systemd with a minimal environment or as
    root. In that case Path.home() and PATH do not describe the interactive
    user installation. The search remains bounded to known local accounts.
    """
    homes: list[Path] = []

    def add(raw: str | os.PathLike[str] | None) -> None:
        if not raw:
            return
        path = Path(raw).expanduser()
        if path.is_dir() and path not in homes:
            homes.append(path)

    add(os.environ.get("HOME"))
    add(Path.home())

    for name in (os.environ.get("USER"), os.environ.get("LOGNAME"), os.environ.get("SUDO_USER")):
        if not name:
            continue
        try:
            add(pwd.getpwnam(name).pw_dir)
        except KeyError:
            pass

    if os.geteuid() == 0:
        for account in pwd.getpwall():
            if account.pw_uid >= 1000 and account.pw_dir not in {"/", "/nonexistent"}:
                add(account.pw_dir)

    return homes


def candidate_search_paths() -> list[Path]:
    """Build a deterministic executable search path for service and shell installs."""
    paths: list[Path] = []

    def add(raw: str | os.PathLike[str] | None) -> None:
        if not raw:
            return
        path = Path(raw).expanduser()
        if path.is_dir() and path not in paths:
            paths.append(path)

    for raw in os.environ.get("PATH", "").split(os.pathsep):
        add(raw)

    for raw in ("/usr/local/sbin", "/usr/local/bin", "/usr/sbin", "/usr/bin", "/sbin", "/bin"):
        add(raw)

    for home in candidate_homes():
        for relative in (
            ".local/bin",
            "bin",
            ".kimi-code/bin",
            ".npm-global/bin",
            ".local/share/pnpm",
            ".bun/bin",
            ".deno/bin",
            ".cargo/bin",
            ".volta/bin",
            ".asdf/shims",
            ".local/share/mise/shims",
        ):
            add(home / relative)
        for pattern in (
            ".nvm/versions/node/*/bin",
            ".local/share/mise/installs/node/*/bin",
            ".asdf/installs/nodejs/*/bin",
        ):
            for path in sorted(home.glob(pattern), reverse=True):
                add(path)

    return paths


def discovery_environment() -> dict[str, str]:
    environment = {**os.environ, "LC_ALL": "C", "LANG": "C"}
    environment["PATH"] = os.pathsep.join(str(path) for path in candidate_search_paths())
    return environment


def resolve_command(command: str) -> str | None:
    if os.sep in command:
        path = Path(command).expanduser()
        return str(path) if path.is_file() and os.access(path, os.X_OK) else None
    search_path = os.pathsep.join(str(path) for path in candidate_search_paths())
    return shutil.which(command, path=search_path)


def command_exists(command: str) -> bool:
    return resolve_command(command) is not None


def run(command: list[str], timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=discovery_environment(),
        )
        return {
            "command": command,
            "available": True,
            "return_code": completed.returncode,
            "stdout": redact(completed.stdout.strip()),
            "stderr": redact(completed.stderr.strip()),
            "duration_ms": round((time.monotonic() - started) * 1000),
        }
    except FileNotFoundError:
        return {"command": command, "available": False, "error": "command_not_found"}
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "available": True,
            "error": "timeout",
            "timeout_seconds": timeout,
            "stdout": redact((exc.stdout or "").strip() if isinstance(exc.stdout, str) else ""),
            "stderr": redact((exc.stderr or "").strip() if isinstance(exc.stderr, str) else ""),
        }
    except OSError as exc:
        return {"command": command, "available": True, "error": type(exc).__name__, "message": str(exc)}


def read_text(path: str, limit: int = 131072) -> str | None:
    try:
        return redact(Path(path).read_text(encoding="utf-8", errors="replace")[:limit])
    except (OSError, PermissionError):
        return None


def versions(
    commands: dict[str, list[str]],
    *,
    timeout: int = DEFAULT_VERSION_TIMEOUT,
    max_workers: int = DEFAULT_VERSION_WORKERS,
) -> dict[str, Any]:
    """Probe independent version commands concurrently with bounded latency."""
    results: dict[str, Any] = {}
    runnable: dict[str, list[str]] = {}
    resolved_paths: dict[str, str] = {}
    for name, command in commands.items():
        resolved = resolve_command(command[0])
        if resolved:
            runnable[name] = [resolved, *command[1:]]
            resolved_paths[name] = resolved
        else:
            results[name] = {"available": False}

    if runnable:
        workers = max(1, min(max_workers, len(runnable)))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="aiops-discovery") as executor:
            futures = {
                executor.submit(run, command, timeout): name
                for name, command in runnable.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    result["resolved_path"] = resolved_paths[name]
                    results[name] = result
                except Exception as exc:  # individual probe isolation is intentional
                    results[name] = {
                        "command": runnable[name],
                        "resolved_path": resolved_paths[name],
                        "available": True,
                        "error": type(exc).__name__,
                        "message": str(exc),
                    }

    return {name: results[name] for name in commands}


def collect_system() -> dict[str, Any]:
    return {
        "hostname": socket.gethostname(),
        "fqdn": socket.getfqdn(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "os_release": read_text("/etc/os-release"),
        "kernel": run(["uname", "-a"]),
        "uptime": run(["uptime"]),
        "cpu": run(["lscpu"]),
        "memory": run(["free", "-b"]),
        "block_devices": run(["lsblk", "--json", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS,MODEL,SERIAL"]),
        "filesystems": run(["df", "-PT"]),
        "mounts": run(["findmnt", "--json"]),
        "failed_units": run(["systemctl", "--failed", "--no-pager"]) if command_exists("systemctl") else {"available": False},
    }


def collect_network() -> dict[str, Any]:
    return {
        "addresses": run(["ip", "-json", "address"]),
        "routes": run(["ip", "-json", "route"]),
        "listeners": run(["ss", "-lntup"]),
        "dns": read_text("/etc/resolv.conf"),
        "hosts": read_text("/etc/hosts"),
        "tailscale": versions({
            "version": ["tailscale", "version"],
            "status": ["tailscale", "status", "--json"],
            "ipv4": ["tailscale", "ip", "-4"],
        }),
        "firewall": versions({
            "ufw": ["ufw", "status", "verbose"],
            "nftables": ["nft", "list", "ruleset"],
            "iptables": ["iptables", "-S"],
        }),
    }


def collect_services() -> dict[str, Any]:
    if not command_exists("systemctl"):
        return {"systemd": {"available": False}}
    return {
        "systemd": {
            "version": run(["systemctl", "--version"]),
            "services": run(["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--plain"], timeout=15),
            "service_files": run(["systemctl", "list-unit-files", "--type=service", "--no-pager", "--plain"], timeout=15),
            "timers": run(["systemctl", "list-timers", "--all", "--no-pager", "--plain"]),
        },
        "cron": {
            "system_crontab": read_text("/etc/crontab"),
            "directories": [str(p) for p in map(Path, ["/etc/cron.d", "/etc/cron.daily", "/etc/cron.hourly", "/etc/cron.weekly"]) if p.exists()],
        },
    }


def collect_containers() -> dict[str, Any]:
    return {
        "docker": versions({
            "version": ["docker", "version", "--format", "{{json .}}"],
            "info": ["docker", "info", "--format", "{{json .}}"],
            "containers": ["docker", "ps", "-a", "--no-trunc", "--format", "{{json .}}"],
            "images": ["docker", "images", "--digests", "--no-trunc", "--format", "{{json .}}"],
            "networks": ["docker", "network", "ls", "--format", "{{json .}}"],
            "compose": ["docker", "compose", "ls", "--format", "json"],
        }),
        "podman": versions({
            "version": ["podman", "version", "--format", "json"],
            "info": ["podman", "info", "--format", "json"],
            "containers": ["podman", "ps", "-a", "--format", "json"],
        }),
        "kubernetes": versions({
            "kubectl": ["kubectl", "version", "--client", "-o", "json"],
            "contexts": ["kubectl", "config", "get-contexts", "-o", "name"],
        }),
    }


def collect_development() -> dict[str, Any]:
    tools = {
        "git": ["git", "--version"], "gh": ["gh", "--version"],
        "python3": ["python3", "--version"], "uv": ["uv", "--version"],
        "pipx": ["pipx", "--version"], "node": ["node", "--version"],
        "npm": ["npm", "--version"], "pnpm": ["pnpm", "--version"],
        "java": ["java", "-version"], "go": ["go", "version"],
        "rustc": ["rustc", "--version"], "docker": ["docker", "--version"],
        "openapi_generator": ["openapi-generator-cli", "version"],
    }
    git_context = versions({
        "root": ["git", "rev-parse", "--show-toplevel"],
        "branch": ["git", "branch", "--show-current"],
        "status": ["git", "status", "--short"],
        "remotes": ["git", "remote", "-v"],
    })
    return {"tools": versions(tools), "git_context": git_context}


def collect_ai() -> dict[str, Any]:
    agents = {
        "kimi": ["kimi", "-V"], "claude": ["claude", "--version"],
        "codex": ["codex", "--version"], "opencode": ["opencode", "--version"],
        "gemini": ["gemini", "--version"], "aider": ["aider", "--version"],
        "ollama": ["ollama", "--version"], "pai": ["pai", "--version"],
    }
    names = sorted(name for name in os.environ if re.search(
        r"OPENAI|ANTHROPIC|GEMINI|GOOGLE|MISTRAL|GROQ|OPENROUTER|OLLAMA|LITELLM|NEW.?API|CLI.?PROXY|MCP|CODEX|CLAUDE|KIMI",
        name,
        re.I,
    ))
    config_relatives = [
        ".claude", ".codex", ".kimi", ".kimi-code",
        ".config/opencode", ".opencode", ".config/kimi",
    ]
    configs: list[str] = []
    for home in candidate_homes():
        for relative in config_relatives:
            root = home / relative
            if root.exists() and str(root) not in configs:
                configs.append(str(root))
    return {
        "agents_and_gateways": versions(agents),
        "environment_variable_names": names,
        "known_config_roots": configs,
        "searched_homes": [str(path) for path in candidate_homes()],
        "searched_executable_paths": [str(path) for path in candidate_search_paths()],
        "related_processes": run(["ps", "auxww"]),
    }


def collect_platform_services() -> dict[str, Any]:
    tools = {
        "nginx": ["nginx", "-v"], "caddy": ["caddy", "version"],
        "traefik": ["traefik", "version"], "apache": ["apache2", "-v"],
        "prometheus": ["prometheus", "--version"], "grafana": ["grafana", "-v"],
        "postgres": ["psql", "--version"], "mysql": ["mysql", "--version"],
        "redis": ["redis-server", "--version"], "restic": ["restic", "version"],
        "borg": ["borg", "--version"], "rclone": ["rclone", "version"],
    }
    return {"tools": versions(tools)}


COLLECTORS: dict[str, Callable[[], dict[str, Any]]] = {
    "system": collect_system,
    "network": collect_network,
    "services": collect_services,
    "containers": collect_containers,
    "development": collect_development,
    "ai": collect_ai,
    "platform": collect_platform_services,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-OPS AIS-0003 read-only system discovery")
    parser.add_argument("--output", "-o", type=Path, help="Write report to this JSON file")
    parser.add_argument("--collect", default=",".join(COLLECTORS), help="Comma-separated collector names")
    parser.add_argument("--compact", action="store_true", help="Write compact JSON")
    parser.add_argument("--list-collectors", action="store_true", help="List collectors and exit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.list_collectors:
        print("\n".join(COLLECTORS))
        return 0

    selected = [name.strip() for name in args.collect.split(",") if name.strip()]
    unknown = sorted(set(selected) - set(COLLECTORS))
    if unknown:
        print(f"Unknown collectors: {', '.join(unknown)}", file=sys.stderr)
        return 2

    report: dict[str, Any] = {
        "schema_version": "0.1.0",
        "report_id": str(uuid.uuid4()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": {"name": "aiops-discovery", "version": VERSION},
        "mode": "read_only",
        "effective_user": {"uid": os.geteuid(), "gid": os.getegid(), "name": os.environ.get("USER")},
        "collectors": {},
        "errors": [],
    }

    for name in selected:
        try:
            report["collectors"][name] = COLLECTORS[name]()
        except Exception as exc:  # collector isolation is intentional
            report["errors"].append({"collector": name, "error": type(exc).__name__, "message": str(exc)})

    payload = json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(args.output)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
