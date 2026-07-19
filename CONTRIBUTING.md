# Contributing to AI-OPS Standard

Thank you for contributing to AI-OPS Standard. The project combines normative specifications, a reference implementation, schemas, tests and operational documentation. Changes must preserve safety, determinism and auditability.

## Before opening a change

1. Search existing issues and RFCs.
2. For normative or architectural changes, open an RFC or discussion issue first.
3. Keep each pull request focused on one problem.
4. Do not include credentials, access tokens, private hostnames, production data or customer information.

## Development setup

```bash
git clone https://github.com/agro0305/ai-ops-standard.git
cd ai-ops-standard
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip pytest
```

## Required checks

Run all checks before submitting a pull request:

```bash
python3 scripts/validate_repository.py
python3 -m pytest -q compliance/tests
python3 scripts/acceptance.py --project-root . --output acceptance-result.json
```

The acceptance suite must remain non-destructive and use temporary paths only.

## Specification changes

- English documents are canonical.
- Serbian translations use the `.sr.md` suffix.
- Preserve document metadata and semantic versions.
- State whether a requirement is normative using MUST, SHOULD or MAY.
- Update schemas, examples and compliance tests when a normative record changes.

## Implementation changes

- Discovery must remain read-only.
- State-changing operations must be dry-run by default.
- High-risk operations require explicit approval.
- Backups and rollback records must be bound to the exact plan digest.
- Never invoke a shell for arbitrary command execution.
- Add regression tests for every fixed defect.

## Pull request description

Explain:

- the problem being solved;
- the safety impact;
- files and interfaces changed;
- tests executed;
- rollback or compatibility considerations.

By contributing, you agree that your contribution is licensed under Apache License 2.0.
