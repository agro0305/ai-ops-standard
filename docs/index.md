# AI-OPS Standard

AI-OPS Standard is an open standard and reference implementation for safe, repeatable and auditable AI operations on Linux infrastructure, MCP servers and AI coding agents.

The project defines a complete operational lifecycle:

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

## Current release

Version **0.2.0** is the first validated reference implementation release candidate.

It includes:

- read-only system, development and AI capability discovery;
- deterministic compliance checks;
- authenticated local dashboard and Prometheus metrics;
- atomic scheduled report refresh;
- verified backup manifests tied to the exact operation plan;
- dry-run-by-default execution and rollback;
- incident lifecycle, notifications and retention;
- non-destructive acceptance testing and runtime health checks.

## Start here

- [Read the standard overview](standard.md)
- [Install or upgrade the reference implementation](INSTALLATION.md)
- [Read the 0.2.0 release notes](releases/0.2.0.md)
- [Contribute or request support](community.md)

## Repository

The source code, normative specifications, schemas and compliance suite are hosted at:

[github.com/agro0305/ai-ops-standard](https://github.com/agro0305/ai-ops-standard)

The project is licensed under Apache License 2.0.
