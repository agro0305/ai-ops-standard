# Automatic AI-OPS Report Refresh

The reference refresh pipeline regenerates the latest dashboard data without interrupting the dashboard service.

## Pipeline

```text
Discovery → AI/MCP Capability Registry → Compliance → Atomic publish
```

The pipeline writes:

- `discovery-report.json`;
- `ai-capability-registry.json`;
- `compliance-result.json`;
- `refresh-status.json`.

Reports are generated in a temporary directory, parsed as JSON and published only when the complete pipeline is valid. A failed run preserves the previous successful reports and updates only `refresh-status.json`.

A non-passing compliance result is a valid report and does not make the refresh pipeline fail. Compliance still records its failed requirements and exits with its normal non-zero compliance status.

## Manual refresh

```bash
python3 scripts/refresh_reports.py \
  --project-root . \
  --output-dir .
```

The process uses a non-blocking file lock. A second refresh exits without running while the first refresh is active.

## systemd timer installation

Review the plan without changing the system:

```bash
bash dashboard/install_refresh_timer.sh
```

Install the timer with the default 15-minute interval:

```bash
sudo bash dashboard/install_refresh_timer.sh --apply
```

Use another interval:

```bash
sudo bash dashboard/install_refresh_timer.sh \
  --interval 30min \
  --apply
```

Accepted interval suffixes are `s`, `min`, `h` and `d`.

## Verification

```bash
systemctl status aiops-report-refresh.timer --no-pager
systemctl status aiops-report-refresh.service --no-pager
systemctl list-timers aiops-report-refresh.timer --no-pager
journalctl -u aiops-report-refresh.service -n 100 --no-pager
```

Force an immediate refresh:

```bash
sudo systemctl start aiops-report-refresh.service
```

Inspect the latest pipeline status:

```bash
python3 -m json.tool refresh-status.json
```

## Safety properties

- dry-run installation by default;
- backup of existing service and timer units before replacement;
- no firewall changes;
- service runs as the selected unprivileged user;
- one active refresh at a time;
- temporary generation followed by atomic publication;
- previous successful reports survive failed refreshes;
- systemd write access is limited to the configured output directory;
- dashboard restart is not required after report refresh.
