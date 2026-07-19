# AI-OPS Dashboard

The dashboard is a local-first, read-only-by-default view of AI-OPS inventory, operations and compliance.

## Current reference implementation

The current server indexes JSON reports and provides:

- `/` — report index;
- `/api/reports` — machine-readable report contents;
- `/healthz` — minimal unauthenticated health response;
- automatic free-port selection for foreground use;
- Local, LAN and Tailscale URL discovery;
- optional Basic, Bearer and header-token authentication;
- a safe systemd installer.

## Foreground use

Local-only:

```bash
python3 dashboard/server.py --data-dir .
```

LAN and Tailscale with token authentication:

```bash
python3 - <<'PY' > ~/.aiops-dashboard.token
import secrets
print(secrets.token_urlsafe(32))
PY
chmod 600 ~/.aiops-dashboard.token

python3 dashboard/server.py \
  --data-dir . \
  --host 0.0.0.0 \
  --port 8787 \
  --auth-token-file ~/.aiops-dashboard.token
```

The server checks the requested port and automatically chooses the next free port unless `--strict-port` is supplied.

## Authentication

When opening the dashboard in a browser, use:

```text
Username: aiops
Password: contents of the token file
```

API clients may use:

```text
Authorization: Bearer <token>
```

or:

```text
X-AI-OPS-Token: <token>
```

The `/healthz` endpoint remains unauthenticated and returns no report contents.

Example API request:

```bash
curl -H "Authorization: Bearer $(cat ~/.aiops-dashboard.token)" \
  http://127.0.0.1:8789/api/reports
```

Basic and Bearer credentials over plain HTTP are not encrypted. For access outside a trusted LAN, use Tailscale or a reverse proxy with TLS.

## systemd installation

Review the installation plan without making changes:

```bash
bash dashboard/install_systemd.sh
```

Apply after reviewing the discovered port, user, paths and backup location:

```bash
sudo bash dashboard/install_systemd.sh --apply
```

The installer:

- checks the preferred port and selects a free port;
- does not modify firewall rules;
- backs up an existing unit and token before replacement;
- creates a random token outside the repository;
- enables a hardened systemd service;
- uses strict-port mode so the service address remains stable;
- preserves an existing non-empty token file.

Status and logs:

```bash
systemctl status aiops-dashboard --no-pager
journalctl -u aiops-dashboard -n 100 --no-pager
```

Read the generated token:

```bash
sudo cat /etc/aiops-dashboard.token
```

Uninstalling is intentionally manual:

```bash
sudo systemctl disable --now aiops-dashboard
sudo rm /etc/systemd/system/aiops-dashboard.service
sudo systemctl daemon-reload
```

The token and backups are not deleted automatically.

## Required future views

- Overview
- System Inventory
- AI Capability Registry
- MCP Registry
- Operations
- Backups
- Verification
- Rollback
- Compliance
- Alerts and Audit

## Deployment principles

- Operates on localhost, LAN and Tailscale.
- Does not require public internet exposure.
- Uses authenticated backend APIs for control operations.
- Never treats UI state as source of truth.
- Redacts secrets and sensitive payloads.
- Keeps state-changing operations outside the current read-only server.
