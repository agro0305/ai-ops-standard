# Support

AI-OPS Standard is an open-source reference implementation and draft standard.

## Questions and usage help

Use GitHub Discussions when enabled, or open an issue using the question/support template. Include the project version, operating system, relevant component and sanitized logs.

## Bug reports

Use the bug-report issue template and provide a minimal reproduction. Run these commands first when applicable:

```bash
python3 scripts/validate_repository.py
python3 -m pytest -q compliance/tests
python3 scripts/runtime_health.py --project-root . --output runtime-health.json
```

Remove tokens, passwords, private hostnames, IP addresses and production data before posting output.

## Security issues

Follow `SECURITY.md`. Do not report exploitable vulnerabilities in public issues.

## Commercial support

No commercial support or service-level agreement is currently offered by the project.
