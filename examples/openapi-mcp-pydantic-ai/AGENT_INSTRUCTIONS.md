# Agent instructions: AI-OPS Dashboard MCP

Use the MCP server named `aiops-dashboard` before making infrastructure changes.

## Required pre-check

1. Call `getHealth`.
2. Call `getReadiness`.
3. Continue only when health is `ok` and readiness is `ready`.
4. Stop and report the returned state when either check fails.

## Current scope

This integration is read-only and exposes only dashboard status checks.

It does not prove that the following lifecycle stages were completed:

- planning;
- approval;
- backup;
- execution;
- verification;
- rollback;
- audit recording.

Do not claim that any of those stages happened unless separate AI-OPS evidence exists.

## Prompt to give an agent

```text
Before changing infrastructure, use the aiops-dashboard MCP server.
Call getHealth and getReadiness. Continue only when health is ok and
readiness is ready. Treat these tools only as status checks; do not claim
that backup, execution, verification, rollback or audit were completed.
```
