#!/usr/bin/env bash
set -euo pipefail

APPLY=0
INTERVAL="15min"
SERVICE_NAME="aiops-report-refresh"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$PROJECT_ROOT"
SERVICE_USER="${SUDO_USER:-${USER:-$(id -un)}}"

usage() {
  cat <<'EOF'
Usage: dashboard/install_refresh_timer.sh [options]

Options:
  --apply                  Apply changes. Without this flag the script is dry-run.
  --interval VALUE         systemd interval: number + s|min|h|d (default: 15min).
  --user USER              Service account (default: current/SUDO_USER).
  --project-root PATH      AI-OPS repository root.
  --output-dir PATH        Directory for latest JSON reports (default: repository root).
  -h, --help               Show help.
EOF
}

while (($#)); do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --user) SERVICE_USER="$2"; shift 2 ;;
    --project-root) PROJECT_ROOT="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

PROJECT_ROOT="$(readlink -f "$PROJECT_ROOT")"
mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(readlink -f "$OUTPUT_DIR")"
REFRESH_SCRIPT="$PROJECT_ROOT/scripts/refresh_reports.py"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
TIMER_FILE="/etc/systemd/system/${SERVICE_NAME}.timer"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="/var/backups/${SERVICE_NAME}/${TIMESTAMP}"

[[ -f "$REFRESH_SCRIPT" ]] || { echo "Missing refresh script: $REFRESH_SCRIPT" >&2; exit 1; }
[[ -d "$OUTPUT_DIR" ]] || { echo "Missing output directory: $OUTPUT_DIR" >&2; exit 1; }
id "$SERVICE_USER" >/dev/null 2>&1 || { echo "Unknown service user: $SERVICE_USER" >&2; exit 1; }
[[ "$INTERVAL" =~ ^[1-9][0-9]*(s|min|h|d)$ ]] || { echo "Invalid interval: $INTERVAL" >&2; exit 1; }
[[ "$PROJECT_ROOT" != *$'\n'* && "$PROJECT_ROOT" != *' '* ]] || { echo "Project path must not contain spaces or newlines" >&2; exit 1; }
[[ "$OUTPUT_DIR" != *$'\n'* && "$OUTPUT_DIR" != *' '* ]] || { echo "Output path must not contain spaces or newlines" >&2; exit 1; }

SERVICE_GROUP="$(id -gn "$SERVICE_USER")"

echo "AI-OPS report refresh timer installation plan"
echo "  Mode:         $([[ $APPLY -eq 1 ]] && echo APPLY || echo DRY-RUN)"
echo "  Project:      $PROJECT_ROOT"
echo "  Output:       $OUTPUT_DIR"
echo "  Service user: $SERVICE_USER"
echo "  Interval:     $INTERVAL"
echo "  Service:      $SERVICE_FILE"
echo "  Timer:        $TIMER_FILE"
echo "  Backup:       $BACKUP_DIR"
echo "  Firewall:     unchanged"

if [[ $APPLY -ne 1 ]]; then
  echo "No changes made. Re-run with --apply after reviewing the plan."
  exit 0
fi

[[ $EUID -eq 0 ]] || { echo "Apply mode must be run with sudo/root." >&2; exit 1; }

mkdir -p "$BACKUP_DIR"
for path in "$SERVICE_FILE" "$TIMER_FILE"; do
  if [[ -e "$path" ]]; then
    cp -a "$path" "$BACKUP_DIR/"
  fi
done

cat >"$SERVICE_FILE" <<EOF
[Unit]
Description=Refresh AI-OPS discovery, capability and compliance reports
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$PROJECT_ROOT
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 $REFRESH_SCRIPT --project-root $PROJECT_ROOT --output-dir $OUTPUT_DIR
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$OUTPUT_DIR
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
LockPersonality=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=6

[Install]
WantedBy=multi-user.target
EOF
chmod 0644 "$SERVICE_FILE"

cat >"$TIMER_FILE" <<EOF
[Unit]
Description=Periodically refresh AI-OPS reports

[Timer]
OnBootSec=2min
OnUnitActiveSec=$INTERVAL
RandomizedDelaySec=30s
Persistent=true
Unit=${SERVICE_NAME}.service

[Install]
WantedBy=timers.target
EOF
chmod 0644 "$TIMER_FILE"

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.timer"
systemctl start "${SERVICE_NAME}.service"
systemctl --no-pager --full status "${SERVICE_NAME}.timer"

echo
echo "Installation complete."
echo "Backup directory: $BACKUP_DIR"
echo "Check latest run: systemctl status ${SERVICE_NAME}.service --no-pager"
echo "Check schedule: systemctl list-timers ${SERVICE_NAME}.timer --no-pager"
