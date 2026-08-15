# AGENTS.md

All AI agents MUST follow:

```text
Discovery → Analysis → Plan → Approval → Backup → Execution → Verification → Rollback Decision → Audit
```

Mandatory rules:

1. Inspect current state before changes.
2. Do not assume tools, ports, services or MCP servers are absent.
3. Back up before modifying existing configuration.
4. Preserve existing services unless explicitly requested otherwise.
5. Use the smallest possible change.
6. Verify every change.
7. Provide rollback instructions.
8. Produce a structured operation report.
9. Never expose secrets.
10. Stop before destructive or safety-critical actions without explicit approval.

## AI-OPS MCP skill

For infrastructure, service, deployment, configuration, migration, repair or other operational work, load and follow:

```text
.agents/skills/ai-ops-mcp/SKILL.md
```

Current MCP server: `aiops-dashboard`.

Current tools are read-only status checks:

- `getHealth`
- `getReadiness`

Call both tools once at the beginning of one infrastructure task. Reuse that result for the task. Do not repeat the same checks after every message or command unless the MCP/dashboard restarted, connectivity failed, the result became stale, or the user explicitly requested a new check.

Do not use this MCP pre-check for ordinary documentation, code refactoring or isolated local tests that do not affect infrastructure.

The current MCP integration does not perform or prove plan, approval, backup, execution, verification, rollback or audit stages. Never claim otherwise.
\n\n

## Mandatory automated development workflow (RUNBOOK 02)

The primary working repository is local. Required remotes:

- `local` = local bare Git mirror
- `origin` = GitHub

For non-trivial tasks:

1. Check `git status --short`, current branch, and remotes before editing.
2. Preserve unrelated local work. Never reset, delete, overwrite, force-push, or auto-merge it.
3. Make only the required change. Run existing tests/build/lint where applicable.
4. Commit locally.
5. Run `/usr/local/bin/git-sync-all "$(git rev-parse --show-toplevel)"`.
6. Never bypass hooks with `--no-verify`.
7. Verify GitHub Actions after the GitHub push. Read exact failures and make only focused, task-relevant fixes; stop after a reasonable bounded attempt.
8. Never invent scanner or CI results. Never claim PASS unless the step actually ran and passed.
9. Use SonarQube and Trivy for the configured vulnerability, secret, dependency, container, IaC, and misconfiguration gates. Prioritize NEW, HIGH/CRITICAL, actionable, task-relevant findings.
10. Treat a real discovered secret as compromised and never print its full value.
11. Prefer LAN locally and Tailscale remotely. Never expose SonarQube publicly.

Completion requires, where applicable: local change complete, tests/build/lint passed, commit created, local mirror push passed, GitHub push passed, and GitHub Actions passed. If an external service is unavailable or a gate fails, report the exact failed or unverified step.

For documentation-only or trivial changes, do not invent tests that do not exist; Git sync and normal GitHub Actions still apply when committing.

After reboot, expect systemd to restore Docker, Tailscale, SonarQube, GitHub runner, and automation timers. Report inactive services before changing infrastructure.
