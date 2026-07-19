# Changelog

All notable project changes are documented here.

## 0.2.0 — 2026-07-19

### Added

- Linux discovery reference implementation and compliance tests.
- AI coding-agent and MCP capability registry.
- Deterministic compliance runner.
- Local-first authenticated dashboard with report browsing, alerts, audit events, metrics and freshness monitoring.
- Safe systemd installers for dashboard, report refresh, retention, incidents and notifications.
- Atomic report refresh with append-only audit events.
- Deterministic notification dispatcher with cooldown and deduplication.
- Incident lifecycle manager with active, acknowledged, silenced and resolved states.
- Incident-aware notification suppression.
- Backup retention and rotated audit-log retention.
- JSON schemas for plans, backups, execution, verification, rollback, refresh, notifications and incidents.

### Changed

- Operation plans now normalize target paths and reject exact protected system roots.
- All filesystem action targets, including `mkdir`, are backed up.
- Apply execution now requires a complete verified manifest when backup is required.
- Backup manifests are bound to the exact plan digest and target set.
- Command actions require explicit rollback argv arrays and never use a shell.
- Rollback is dry-run by default and requires `--apply` to restore data.
- Rollback validates backup object digests and verifies restored object digests.
- Execution reports no longer copy file content or full command argv arrays into action descriptors.

### Security

- Added symlink-write protections.
- Added path-traversal and report-size protections in the dashboard.
- Added Basic/Bearer/header-token authentication and security response headers.
- Moved dashboard tokens, webhook credentials, notification state and private incident state outside report-visible data.
- Added hardened systemd unit settings and explicit writable-path boundaries.

## 0.1.0 — 2026-07-18

- Initial draft specifications, schemas, repository validator and basic reference implementations.
