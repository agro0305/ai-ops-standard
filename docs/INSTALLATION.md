# AI-OPS Standard Installation and Upgrade

This guide installs the reference implementation on one Linux host. All installers are dry-run unless `--apply` is supplied.

## Prerequisites

- Python 3.12 or newer;
- systemd;
- a dedicated non-root service user or the repository owner;
- repository checked out on a local filesystem;
- trusted LAN or Tailscale access when the dashboard binds to `0.0.0.0`.

## 1. Validate the repository

```bash
cd ~/ai-ops-standard
git pull
python3 scripts/validate_repository.py
python3 -m pytest -q compliance/tests
python3 scripts/acceptance.py --project-root .
```

Do not continue when validation or acceptance fails.

## 2. Dashboard

Review:

```bash
bash dashboard/install_systemd.sh
```

Install:

```bash
sudo bash dashboard/install_systemd.sh --apply
```

Check:

```bash
systemctl status aiops-dashboard --no-pager
curl -fsS http://127.0.0.1:8789/healthz
curl -fsS http://127.0.0.1:8789/readyz
```

Read the generated login token:

```bash
sudo cat /etc/aiops-dashboard.token
```

## 3. Automatic report refresh

Review and install:

```bash
bash dashboard/install_refresh_timer.sh
sudo bash dashboard/install_refresh_timer.sh --apply
```

Run once and check:

```bash
sudo systemctl start aiops-report-refresh.service
systemctl status aiops-report-refresh.service --no-pager
systemctl list-timers aiops-report-refresh.timer --no-pager
```

The oneshot service should become `inactive (dead)` after a successful run. The timer should remain `active (waiting)`.

## 4. Incident lifecycle

Review and install:

```bash
bash dashboard/install_incident_timer.sh
sudo bash dashboard/install_incident_timer.sh --apply
```

Run once and check:

```bash
sudo systemctl start aiops-incidents.service
systemctl status aiops-incidents.service --no-pager
python3 -m json.tool incident-status.json
```

Private incident state is stored at:

```text
.aiops-incidents/state.json.private
```

It is not exposed by the dashboard report API.

## 5. Notifications

Review and install:

```bash
bash dashboard/install_notification_timer.sh
sudo bash dashboard/install_notification_timer.sh --apply
```

The default channel writes to the systemd journal. Webhook delivery remains disabled until explicitly enabled in:

```text
/etc/aiops-notifications.json
```

Webhook URL and token belong only in:

```text
/etc/aiops-notifications.env
```

Run once and check:

```bash
sudo systemctl start aiops-notifications.service
journalctl -u aiops-notifications.service -n 100 --no-pager
```

Acknowledged, silenced and resolved incidents are suppressed by the incident-aware notifier.

## 6. Retention

Review and install:

```bash
bash dashboard/install_retention_timer.sh
sudo bash dashboard/install_retention_timer.sh --apply
```

The default policy retains backup directories for 30 days and rotated audit logs for 90 days. The active audit log and current reports are never selected.

## 7. Runtime health check

```bash
python3 scripts/runtime_health.py \
  --project-root . \
  --dashboard-url http://127.0.0.1:8789 \
  --require-services \
  --output runtime-health.json
```

## Upgrade procedure

```bash
cd ~/ai-ops-standard
git pull
python3 scripts/validate_repository.py
python3 -m pytest -q compliance/tests
python3 scripts/acceptance.py --project-root .
sudo systemctl restart aiops-dashboard
sudo systemctl start aiops-report-refresh.service
sudo systemctl start aiops-incidents.service
```

Re-run an installer only when its unit definition or configuration layout changed. Installers back up existing unit/configuration files before replacement.

## Recommended service order

```text
aiops-report-refresh.service
        ↓
aiops-incidents.service
        ↓
aiops-notifications.service
```

Retention is independent and runs weekly. The dashboard reads the latest generated files and does not need restart after each refresh.
