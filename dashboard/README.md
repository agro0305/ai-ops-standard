# AI-OPS Dashboard

The dashboard is a local-first, read-only-by-default view of AI-OPS inventory, operations and compliance.

## Current reference implementation

The current dashboard provides:

- an operational overview with report, freshness, alert and compliance counters;
- automatic classification of discovery, capability, refresh, compliance, plan, backup, execution, verification and rollback reports;
- filtering and search by report type, file name and plan metadata;
- safe opening and copying of individual JSON reports;
- recursive discovery of nested backup manifests;
- freshness checks for automatically refreshed reports;
- alerts for stale reports, refresh failures, invalid JSON, compliance failures and failed operations;
- `/api/summary` — dashboard aggregate status;
- `/api/alerts` — current deterministic alerts;
- `/api/reports` — report metadata without full payloads;
- `/api/reports/<name>` — one validated report;
- `/healthz` — minimal liveness response;
- `/readyz` — data-directory readiness response;
- Local, LAN and Tailscale URL discovery;
- optional Basic, Bearer and header-token authentication;
- safe systemd installers for the dashboard and report refresh timer.

Reports larger than 10 MiB are not opened by the reference UI. Symlinked reports, path traversal and files outside the configured data directory are rejected.

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

The `/healthz` and `/readyz` endpoints remain unauthenticated and return no report contents.

Example API requests:

```bash
TOKEN="$(cat ~/.aiops-dashboard.token)"

curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8789/api/summary

curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8789/api/alerts

curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8789/api/reports
```

Basic and Bearer credentials over plain HTTP are not encrypted. For access outside a trusted LAN, use Tailscale or a reverse proxy with TLS.

## Dashboard systemd installation

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

After updating the repository, restart the service so it loads the new Python and static files:

```bash
sudo systemctl restart aiops-dashboard
systemctl status aiops-dashboard --no-pager
```

Status and logs:

```bash
systemctl status aiops-dashboard --no-pager
journalctl -u aiops-dashboard -n 100 --no-pager
```

Read the generated token:

```bash
sudo cat /etc/aiops-dashboard.token
```

## Automatic report refresh

Review the timer installation plan:

```bash
bash dashboard/install_refresh_timer.sh
```

Install the default 15-minute timer:

```bash
sudo bash dashboard/install_refresh_timer.sh --apply
```

Every refresh atomically regenerates discovery, capability and compliance reports, writes `refresh-status.json`, and appends one event to:

```text
.aiops-audit/events.jsonl
```

The JSONL audit file is rotated to `events.jsonl.1` after 5 MiB. It is intentionally excluded from the report browser, but remains available for audit and external log shipping.

Check timer state and logs:

```bash
systemctl list-timers aiops-report-refresh.timer --no-pager
journalctl -u aiops-report-refresh.service -n 100 --no-pager
```

## Freshness and alerts

The default freshness limit is 45 minutes for:

- `refresh-status.json`;
- `discovery-report.json`;
- `ai-capability-registry.json`;
- `compliance-result.json`.

The dashboard creates deterministic alerts for:

- stale automatic reports;
- failed refresh runs;
- invalid JSON reports;
- failed compliance requirements;
- failed execution, verification or rollback;
- incomplete backups.

Alerts are calculated from report contents and timestamps. They do not modify the system and do not depend on an AI model.

## Data model

The dashboard recognizes reports produced by the reference tools:

- `discovery-report.json`;
- `ai-capability-registry.json`;
- `refresh-status.json`;
- `compliance-result.json`;
- `operation-plan.json`;
- `execution-report.json`;
- `verification-report.json`;
- `rollback-report.json`;
- `.aiops-backups/*/backup-manifest.json`.

Unknown JSON files remain visible under the `other` category.

## Uninstall

Dashboard removal is intentionally manual:

```bash
sudo systemctl disable --now aiops-dashboard
sudo rm /etc/systemd/system/aiops-dashboard.service
sudo systemctl daemon-reload
```

The token, reports, audit events and backups are not deleted automatically.

## Deployment principles

- Operates on localhost, LAN and Tailscale.
- Does not require public internet exposure.
- Uses authenticated backend APIs for report access.
- Never treats UI state as source of truth.
- Redacts secrets before reports reach the dashboard.
- Keeps state-changing operations outside the current read-only server.
- Adds CSP, anti-framing, no-cache and MIME-sniffing protection headers.
