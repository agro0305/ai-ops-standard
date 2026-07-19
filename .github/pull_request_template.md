## Summary

Describe the problem and the focused change.

## Change type

- [ ] Specification / RFC
- [ ] Reference implementation
- [ ] Schema or compliance test
- [ ] Dashboard / observability
- [ ] Documentation / publication
- [ ] Security fix

## Safety impact

Explain effects on discovery, approval, backup, execution, verification, rollback, secrets and audit records.

## Validation

- [ ] `python3 scripts/validate_repository.py`
- [ ] `python3 -m pytest -q compliance/tests`
- [ ] `python3 scripts/acceptance.py --project-root .`
- [ ] Documentation builds with `mkdocs build --strict` when applicable

## Compatibility and rollback

Describe compatibility considerations and how this change can be reverted safely.

## Checklist

- [ ] No credentials, private infrastructure details or production data are included.
- [ ] Regression tests cover fixed defects.
- [ ] Schemas, examples and translations are updated when normative records change.
- [ ] The change remains dry-run by default where state mutation is possible.
