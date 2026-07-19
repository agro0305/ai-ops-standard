# AI-OPS Standard

[![Validate](https://github.com/agro0305/ai-ops-standard/actions/workflows/validate.yml/badge.svg)](https://github.com/agro0305/ai-ops-standard/actions/workflows/validate.yml)
[![Documentation](https://github.com/agro0305/ai-ops-standard/actions/workflows/pages.yml/badge.svg)](https://github.com/agro0305/ai-ops-standard/actions/workflows/pages.yml)
[![Version](https://img.shields.io/badge/version-0.2.0-brightgreen.svg)](docs/releases/0.2.0.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21440196.svg)](https://doi.org/10.5281/zenodo.21440196)

Open standard and reference implementation for safe, repeatable and auditable AI operations on Linux infrastructure, MCP servers and AI coding agents.

AI-OPS defines how an agent discovers current state, plans a minimal change, obtains approval, creates and verifies backups, executes, verifies the result, rolls back safely, manages incidents and produces an audit trail.

- **Documentation:** https://agro0305.github.io/ai-ops-standard/
- **Release notes:** [Version 0.2.0](docs/releases/0.2.0.md)
- **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md)
- **Security:** [SECURITY.md](SECURITY.md)
- **Citation:** [CITATION.cff](CITATION.cff)
- **Archive:** https://doi.org/10.5281/zenodo.21440196

## Project status

- Project version: **0.2.0**
- Release stage: **reference implementation release candidate**
- Specification status: **Draft**
- Canonical language: **English**
- Serbian documentation: maintained in parallel

## Project layers

```text
AI-OPS Standard
├── Specification
├── Reference Implementation
├── Compliance Suite
├── Dashboard and Observability
└── Operations and Incident Lifecycle
```

## Lifecycle

```text
Discovery
  → Capability Registry
  → Analysis
  → Plan
  → Approval
  → Verified Backup
  → Execution
  → Verification
  → Rollback Decision
  → Incident Lifecycle
  → Notification
  → Audit
```

## Implemented capabilities

- Linux system and development-environment discovery;
- AI coding-agent and MCP capability registry;
- deterministic compliance evaluation;
- authenticated local-first dashboard;
- freshness monitoring, alerts, Prometheus metrics and audit browsing;
- atomic scheduled report refresh;
- verified backup manifests bound to the exact operation plan;
- dry-run-by-default execution and rollback;
- protected-root and symlink safeguards;
- incident states: active, acknowledged, silenced and resolved;
- incident-aware notification deduplication and cooldown;
- backup and audit-log retention;
- hardened systemd services and timers;
- full non-destructive release acceptance runner;
- read-only runtime health checker.

## Validate and test

```bash
python3 scripts/validate_repository.py
python3 -m pytest -q compliance/tests
python3 scripts/acceptance.py \
  --project-root . \
  --output acceptance-result.json
```

Acceptance runs the complete safe operation lifecycle in a temporary directory and exercises incident opening, acknowledgement and automatic resolution. It does not modify production paths or services.

## Runtime health

```bash
python3 scripts/runtime_health.py \
  --project-root . \
  --dashboard-url http://127.0.0.1:8789 \
  --require-services \
  --output runtime-health.json
```

## Installation

Use the ordered installation and upgrade procedure in:

```text
docs/INSTALLATION.md
```

The required service order is:

```text
report refresh → incident synchronization → notifications
```

Retention runs independently. The dashboard remains read-only and reads the latest generated reports.

## Specifications

| Document | Title | Status |
|---|---|---|
| AIS-STYLE-0001 | Document Style Guide | Draft |
| AIS-0000 | Introduction | Draft |
| AIS-0001 | Mission | Draft |
| AIS-0002 | Core Principles | Draft |
| AIS-0003 | Discovery | Draft |
| AIS-0004 | Planning | Draft |
| AIS-0005 | Backup | Draft |
| AIS-0006 | Execution | Draft |
| AIS-0007 | Verification | Draft |
| AIS-0008 | Rollback | Draft |
| AIS-0009 | MCP Discovery | Draft |
| AIS-0010 | AI Capability Registry | Draft |
| AIS-0011 | Dashboard | Draft |
| AIS-0012 | Compliance | Draft |

English documents are canonical. Serbian translations use the `.sr.md` suffix.

## Repository

- `specifications/` — normative documents;
- `implementations/` — reference implementations;
- `compliance/` — conformance and safety tests;
- `schemas/` — machine-readable records;
- `dashboard/` — local-first operational UI and systemd installers;
- `scripts/` — refresh, notification, retention, acceptance and health tools;
- `docs/` — installation and operational documentation;
- `templates/` — reports and plans;
- `skills/` — instructions for AI agents;
- `rfcs/` — proposals before standardization.

## Community

- Contributions: [CONTRIBUTING.md](CONTRIBUTING.md)
- Support: [SUPPORT.md](SUPPORT.md)
- Governance: [GOVERNANCE.md](GOVERNANCE.md)
- Code of Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Security reports: [SECURITY.md](SECURITY.md)

## Scope

Initial targets include Ubuntu and other Linux systems, systemd, Docker, Podman, Kubernetes discovery, Git, MCP servers, Kimi Code, Claude Code, Codex CLI, OpenCode, model gateways, OpenAPI, Pydantic AI, local networks and Tailscale.

State-changing adapters for package managers, firewalls, storage controllers and industrial equipment remain domain-specific and require additional policy and safety validation.

## License

Apache License 2.0.
