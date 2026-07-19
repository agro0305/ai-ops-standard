# Security Policy

AI-OPS Standard is designed for operational tooling that may inspect or change infrastructure. Security reports must be handled carefully and should not expose vulnerable systems publicly.

## Supported versions

| Version | Supported |
|---|---|
| 0.2.x | Yes |
| Earlier versions | No |

## Reporting a vulnerability

Do not open a public issue for a vulnerability that could expose credentials, bypass approvals, escape protected paths, alter rollback behavior or permit unintended command execution.

Use GitHub's private vulnerability reporting feature for this repository. Include:

- affected version and commit;
- component and entry point;
- reproduction steps using non-production data;
- expected and actual behavior;
- security impact;
- suggested mitigation, when available.

Do not include real credentials, production host details or customer data.

## Security scope

High-priority reports include:

- path traversal or symlink bypasses;
- execution without required approval or backup;
- plan, manifest or approval digest bypasses;
- exposure of tokens through reports, logs or the dashboard;
- authentication bypasses;
- unsafe shell invocation;
- destructive behavior during dry-run or acceptance testing;
- rollback that restores an unverified or unrelated backup.

## Response process

The project will acknowledge a valid report, reproduce it, prepare a regression test and publish a fixed release. Public disclosure should wait until a fix is available.
