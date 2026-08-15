# Claude Code instructions

Read and follow @AGENTS.md.

For infrastructure, service, deployment, configuration, migration, repair or operational tasks, also read and follow @.agents/skills/ai-ops-mcp/SKILL.md.

Do not load or invoke the AI-OPS MCP workflow for ordinary documentation, code refactoring or isolated local tests that do not affect infrastructure.
\n\n

## Mandatory automated development workflow (RUNBOOK 02)

The primary working repository is local. The required topology is:

- working copy: `/srv/dev/PROJECT`
- local bare mirror: `/srv/git/PROJECT.git`
- GitHub remote: `origin`

For non-trivial tasks:

1. Inspect `git status --short`, `git branch --show-current`, and `git remote -v` before editing.
2. Preserve unrelated local changes. Never reset, delete, overwrite, force-push, or auto-merge them.
3. Make the minimum required change. Run the project's existing tests/build/lint where applicable.
4. Commit the finished local change.
5. Run `/usr/local/bin/git-sync-all "$(git rev-parse --show-toplevel)"`.
6. Never bypass hooks and never use `--no-verify`.
7. Verify GitHub Actions after the GitHub push. If CI fails, read the exact failure and make only a focused, relevant fix; stop after a reasonable bounded attempt.
8. Never claim SonarQube, Trivy, Git sync, GitHub push, or GitHub Actions passed unless they actually ran and passed.
9. Use SonarQube and Trivy as external quality/security gates. Prioritize NEW, HIGH/CRITICAL, actionable, task-relevant findings; do not fix unrelated legacy backlog without a request.
10. Treat any discovered real secret as compromised; never print its full value.
11. Use LAN services locally. Use Tailscale for remote access. Never expose SonarQube publicly.

Completion requires, where applicable: local change complete, tests/build/lint passed, commit created, local mirror push passed, GitHub push passed, and GitHub Actions passed. If an external service is unavailable or a gate fails, report the exact unverified/failed step instead of claiming completion.

For documentation-only or trivial changes, do not invent tests that do not exist; Git sync and the normal GitHub Actions policy still apply when the change is committed.

After reboot, expect systemd to restore Docker, Tailscale, SonarQube, GitHub runner, and automation timers. If one is inactive, report the service failure before changing infrastructure.
