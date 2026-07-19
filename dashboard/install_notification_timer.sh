#!/usr/bin/env bash
set -euo pipefail

APPLY=0
INTERVAL="5min"
SERVICE_NAME="aiops-notifications"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_USER="${SUDO_USER:-${USER:-$(id -un)}}"
CONFIG_SOURCE="$PROJECT_ROOT/examples/notifications.json"
CONFIG_FILE="/etc/${SERVICE_NAME}.json"
ENV_FILE="/etc/${SERVICE_NAME}.env"

usage() {
  cat <<'EOF'
Usage: dashboard/install_notification_timer.sh [options]

Options:
  --apply                  Apply changes. Without this flag the script is dry-run.
  --interval VALUE         systemd interval: number + s|min|h|d (default: 5min).
  --user USER              Service account (default: current/SUDO_USER).
  --project-root PATH      AI-OPS repository root.
  --config-source PATH     Initial JSON config copied only when /etc config is absent.
  -h, --help               Show help.
EOF
}

while (($#)); do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --user) SERVICE_USER="$2"; shift 2 ;;
    --project-root) PROJECT_ROOT="$2"; shift 2 ;;
    --config-source) CONFIG_SOURCE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

PROJECT_ROOT="$(readlink -f "$PROJECT_ROOT")"
CONFIG_SOURCE="$(readlink -f "$CONFIG_SOURCE")"
NOTIFY_SCRIPT="$PROJECT_ROOT/scripts/notify_incident_alerts.py"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
TIMER_FILE="/etc/systemd/system/${SERVICE_NAME}.timer"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="/var/backups/${SERVICE_NAME}/${TIMESTAMP}"

[[ -f "$NOTIFY_SCRIPT" ]] || { echo "Missing notification script: $NOTIFY_SCRIPT" >&2; exit 1; }
[[ -f "$CONFIG_SOURCE" ]] || { echo "Missing notification config example: $CONFIG_SOURCE" >&2; exit 1; }
id "$SERVICE_USER" >/dev/null 2>&1 || { echo "Unknown service user: $SERVICE_USER" >&2; exit 1; }
[[ "$INTERVAL" =~ ^[1-9][0-9]*(s|min|h|d)$ ]] || { echo "Invalid interval: $INTERVAL" >&2; exit 1; }
[[ "$PROJECT_ROOT" != *$'\n'* && "$PROJECT_ROOT" != *' '* ]] || { echo "Project path must not contain spaces or newlines" >&2; exit 1; }
[[ "$CONFIG_SOURCE" != *$'\n'* && "$CONFIG_SOURCE" != *' '* ]] || { echo "Config path must not contain spaces or newlines" >&2; exit 1; }
python3 -m json.tool "$CONFIG_SOURCE" >/dev/null

SERVICE_GROUP="$(id -gn "$SERVICE_USER")"

echo "AI-OPS notification timer installation plan"
echo "  Mode:         $([[ $APPLY -eq 1 ]] && echo APPLY || echo DRY-RUN)"
echo "  Project:      $PROJECT_ROOT"
echo "  Service user: $SERVICE_USER"
echo "  Interval:     $INTERVAL"
echo "  Config:       $CONFIG_FILE"
echo "  Environment:  $ENV_FILE"
echo "  Service:      $SERVICE_FILE"
echo "  Timer:        $TIMER_FILE"
echo "  Backup:       $BACKUP_DIR"
echo "  Incidents:    acknowledged, silenced and resolved alerts are suppressed"
echo "  Immediate run: no"
echo "  Firewall:     unchanged"

if [[ $APPLY -ne 1 ]]; then
  echo "No changes made. Re-run with --apply after reviewing the plan."
  exit 0
fi

[[ $EUID -eq 0 ]] || { echo "Apply mode must be run with sudo/root." >&2; exit 1; }

mkdir -p "$BACKUP_DIR"
for path in "$SERVICE_FILE" "$TIMER_FILE" "$CONFIG_FILE" "$ENV_FILE"; do
  if [[ -e "$path" ]]; then
    cp -a "$path" "$BACKUP_DIR/"
  fi
done

if [[ ! -e "$CONFIG_FILE" ]]; then
  install -o root -g "$SERVICE_GROUP" -m 0640 "$CONFIG_SOURCE" "$CONFIG_FILE"
else
  echo "Preserving existing notification config: $CONFIG_FILE"
fi

if [[ ! -e "$ENV_FILE" ]]; then
  cat >"$ENV_FILE" <<'EOF'
# Enable the webhook channel in /etc/aiops-notifications.json before setting these.
# AIOPS_NOTIFICATION_WEBHOOK_URL=https://alerts.example.invalid/aiops
# AIOPS_NOTIFICATION_TOKEN=replace-me
EOF
  chown root:"$SERVICE_GROUP" "$ENV_FILE"
  chmod 0640 "$ENV_FILE"
else
  echo "Preserving existing notification environment: $ENV_FILE"
fi

cat >"$SERVICE_FILE" <<EOF
[Unit]
Description=Dispatch AI-OPS deterministic alert notifications
Wants=network-online.target aiops-incidents.service
After=network-online.target aiops-report-refresh.service aiops-incidents.service

[Service]
Type=oneshot
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$PROJECT_ROOT
Environment=PYTHONDONTWRITEBYTECODE=1
EnvironmentFile=-$ENV_FILE
ExecStart=/usr/bin/python3 $NOTIFY_SCRIPT --root $PROJECT_ROOT --config $CONFIG_FILE --apply
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$PROJECT_ROOT
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
LockPersonality=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=6
EOF
chmod 0644 "$SERVICE_FILE"

cat >"$TIMER_FILE" <<EOF
[Unit]
Description=Periodically dispatch AI-OPS alert notifications

[Timer]
OnBootSec=5min
OnUnitActiveSec=$INTERVAL
RandomizedDelaySec=20s
Persistent=true
Unit=${SERVICE_NAME}.service

[Install]
WantedBy=timers.target
EOF
chmod 0644 "$TIMER_FILE"

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.timer"
systemctl --no-pager --full status "${SERVICE_NAME}.timer"

echo
echo "Installation complete."
echo "No notification was sent during installation."
echo "Backup directory: $BACKUP_DIR"
echo "Config: $CONFIG_FILE"
echo "Environment: $ENV_FILE"
echo "Dry-run manually: python3 $NOTIFY_SCRIPT --root $PROJECT_ROOT --config $CONFIG_FILE"
echo "Check schedule: systemctl list-timers ${SERVICE_NAME}.timer --no-pager"
