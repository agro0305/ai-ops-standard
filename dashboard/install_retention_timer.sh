#!/usr/bin/env bash
set -euo pipefail

APPLY=0
INTERVAL="7d"
BACKUP_DAYS=30
AUDIT_DAYS=90
SERVICE_NAME="aiops-retention"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_USER="${SUDO_USER:-${USER:-$(id -un)}}"

usage() {
  cat <<'EOF'
Usage: dashboard/install_retention_timer.sh [options]

Options:
  --apply                  Apply changes. Without this flag the script is dry-run.
  --interval VALUE         systemd interval: number + s|min|h|d (default: 7d).
  --backup-days N          Retain backup directories for N days (default: 30).
  --audit-days N           Retain rotated audit logs for N days (default: 90).
  --user USER              Service account (default: current/SUDO_USER).
  --project-root PATH      AI-OPS repository root.
  -h, --help               Show help.
EOF
}

while (($#)); do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --backup-days) BACKUP_DAYS="$2"; shift 2 ;;
    --audit-days) AUDIT_DAYS="$2"; shift 2 ;;
    --user) SERVICE_USER="$2"; shift 2 ;;
    --project-root) PROJECT_ROOT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

PROJECT_ROOT="$(readlink -f "$PROJECT_ROOT")"
RETENTION_SCRIPT="$PROJECT_ROOT/scripts/retention.py"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
TIMER_FILE="/etc/systemd/system/${SERVICE_NAME}.timer"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="/var/backups/${SERVICE_NAME}/${TIMESTAMP}"

[[ -f "$RETENTION_SCRIPT" ]] || { echo "Missing retention script: $RETENTION_SCRIPT" >&2; exit 1; }
id "$SERVICE_USER" >/dev/null 2>&1 || { echo "Unknown service user: $SERVICE_USER" >&2; exit 1; }
[[ "$INTERVAL" =~ ^[1-9][0-9]*(s|min|h|d)$ ]] || { echo "Invalid interval: $INTERVAL" >&2; exit 1; }
[[ "$BACKUP_DAYS" =~ ^[1-9][0-9]*$ ]] || { echo "Invalid backup retention: $BACKUP_DAYS" >&2; exit 1; }
[[ "$AUDIT_DAYS" =~ ^[1-9][0-9]*$ ]] || { echo "Invalid audit retention: $AUDIT_DAYS" >&2; exit 1; }
[[ "$PROJECT_ROOT" != *$'\n'* && "$PROJECT_ROOT" != *' '* ]] || { echo "Project path must not contain spaces or newlines" >&2; exit 1; }

SERVICE_GROUP="$(id -gn "$SERVICE_USER")"

echo "AI-OPS retention timer installation plan"
echo "  Mode:         $([[ $APPLY -eq 1 ]] && echo APPLY || echo DRY-RUN)"
echo "  Project:      $PROJECT_ROOT"
echo "  Service user: $SERVICE_USER"
echo "  Interval:     $INTERVAL"
echo "  Backups:      ${BACKUP_DAYS} days"
echo "  Audit:        ${AUDIT_DAYS} days"
echo "  Service:      $SERVICE_FILE"
echo "  Timer:        $TIMER_FILE"
echo "  Backup:       $BACKUP_DIR"
echo "  Scope:        only .aiops-backups children and rotated .aiops-audit/events.jsonl.* files"

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
Description=Apply AI-OPS backup and audit retention policy

[Service]
Type=oneshot
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$PROJECT_ROOT
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 $RETENTION_SCRIPT --root $PROJECT_ROOT --backup-days $BACKUP_DAYS --audit-days $AUDIT_DAYS --apply
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=-$PROJECT_ROOT/.aiops-backups -$PROJECT_ROOT/.aiops-audit
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
LockPersonality=true
RestrictAddressFamilies=AF_UNIX
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
EOF
chmod 0644 "$SERVICE_FILE"

cat >"$TIMER_FILE" <<EOF
[Unit]
Description=Periodically apply AI-OPS retention policy

[Timer]
OnBootSec=20min
OnUnitActiveSec=$INTERVAL
RandomizedDelaySec=10min
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
echo "Backup directory: $BACKUP_DIR"
echo "Dry-run manually: python3 $RETENTION_SCRIPT --root $PROJECT_ROOT --backup-days $BACKUP_DAYS --audit-days $AUDIT_DAYS"
echo "Check schedule: systemctl list-timers ${SERVICE_NAME}.timer --no-pager"
