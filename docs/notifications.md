# AI-OPS Notifications

The notification dispatcher consumes the same deterministic alerts shown by the dashboard. It does not use an AI model and does not execute shell commands.

## Safety model

- Dry-run is the default.
- Actual dispatch requires `--apply`.
- Critical alerts are selected by default.
- Alert fingerprints prevent duplicate delivery during the cooldown period.
- State is stored in `.aiops-notifications/state.json` and is excluded from the dashboard report index.
- Webhook URLs and tokens are read from environment variables and are never written to reports or audit events.
- HTTPS is required unless a webhook channel explicitly sets `allow_http: true`.
- A failed channel does not update deduplication state, allowing the timer to retry later.

## Manual dry-run

```bash
python3 scripts/notify_alerts.py \
  --root . \
  --config examples/notifications.json
```

Inspect the generated plan/status:

```bash
python3 -m json.tool notification-status.json
```

The example configuration enables only the `stdout` channel. In a systemd service, stdout is recorded in the journal.

## Manual apply with stdout

```bash
python3 scripts/notify_alerts.py \
  --root . \
  --config examples/notifications.json \
  --apply
```

## Generic webhook

Copy the example configuration outside the repository:

```bash
sudo cp examples/notifications.json /etc/aiops-notifications.json
sudo chmod 640 /etc/aiops-notifications.json
```

Set the webhook channel to `enabled: true`, then place secrets in `/etc/aiops-notifications.env`:

```text
AIOPS_NOTIFICATION_WEBHOOK_URL=https://alerts.example.com/aiops
AIOPS_NOTIFICATION_TOKEN=replace-me
```

The dispatcher sends one JSON batch containing the hostname and pending alerts. It supports an optional Bearer token through `AIOPS_NOTIFICATION_TOKEN`.

## systemd timer

Review without changes:

```bash
bash dashboard/install_notification_timer.sh
```

Install the default five-minute timer:

```bash
sudo bash dashboard/install_notification_timer.sh --apply
```

The installer does not dispatch notifications immediately. It preserves existing `/etc/aiops-notifications.json` and `/etc/aiops-notifications.env` files and backs up existing unit files.

Check the timer and latest run:

```bash
systemctl status aiops-notifications.timer --no-pager
systemctl list-timers aiops-notifications.timer --no-pager
systemctl status aiops-notifications.service --no-pager
journalctl -u aiops-notifications.service -n 100 --no-pager
```

Run one dispatch manually through systemd:

```bash
sudo systemctl start aiops-notifications.service
```

## Status and audit

The latest result is written to:

```text
notification-status.json
```

Each execution appends a secret-free `notification-dispatch` event to:

```text
.aiops-audit/events.jsonl
```

The dashboard classifies failed dispatches as critical alerts and treats notification status older than 20 minutes as stale.
