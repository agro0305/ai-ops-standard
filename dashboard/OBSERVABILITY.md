# AI-OPS Observability and Retention

## Authenticated endpoints

The dashboard exposes:

- `/metrics` — Prometheus text format;
- `/api/audit?limit=50` — newest audit events;
- `/api/alerts` — current deterministic alerts;
- `/api/summary` — aggregate report state.

Example:

```bash
TOKEN="$(sudo cat /etc/aiops-dashboard.token)"

curl -s -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8789/metrics

curl -s -H "Authorization: Bearer $TOKEN" \
  'http://127.0.0.1:8789/api/audit?limit=20' | python3 -m json.tool
```

Metrics include report counts, stale and invalid report counts, compliance results, alerts by severity, reports by category and latest refresh state.

## Retention policy

The retention tool is dry-run by default:

```bash
python3 scripts/retention.py \
  --root . \
  --backup-days 30 \
  --audit-days 90
```

It only considers:

- immediate child directories of `.aiops-backups/` older than the backup policy;
- rotated `.aiops-audit/events.jsonl.*` files older than the audit policy.

It never selects the active `.aiops-audit/events.jsonl` file, current JSON reports, repository files or symlinks.

Apply a reviewed plan:

```bash
python3 scripts/retention.py \
  --root . \
  --backup-days 30 \
  --audit-days 90 \
  --apply \
  --output retention-result.json
```

## systemd retention timer

Review the installation plan without changes:

```bash
bash dashboard/install_retention_timer.sh
```

Install a weekly timer using the default 30-day backup and 90-day rotated-audit policy:

```bash
sudo bash dashboard/install_retention_timer.sh --apply
```

Check it:

```bash
systemctl status aiops-retention.timer --no-pager
systemctl list-timers aiops-retention.timer --no-pager
journalctl -u aiops-retention.service -n 100 --no-pager
```

The installer backs up existing unit files before replacement. It does not change firewall rules and does not run retention immediately during installation.
