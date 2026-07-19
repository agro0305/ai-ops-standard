# Governance

AI-OPS Standard is currently maintained under a lightweight maintainer-led governance model.

## Roles

### Maintainer

Maintainers may merge changes, publish releases, manage repository settings and make final decisions when consensus is not reached. The initial maintainer is the repository owner, `agro0305`.

### Contributor

Anyone who submits code, specifications, tests, documentation, reviews or reproducible issue reports is a contributor.

### Reviewer

Trusted contributors may be invited to review specific areas such as specifications, Linux operations, security, schemas or documentation.

## Decision process

- Small fixes may be accepted through a focused pull request.
- Normative, architectural or compatibility-impacting changes require an RFC or tracked design issue.
- Decisions prioritize safety, determinism, auditability, backward compatibility and test coverage.
- Normative English specifications take precedence over translations and implementation behavior.

## Releases

A release requires:

- repository validation;
- the complete compliance test suite;
- successful non-destructive acceptance testing;
- updated version, changelog and release notes;
- no known unresolved critical security defect.

## Conflicts of interest

Reviewers should disclose material conflicts. A contributor should not be the sole approver of a significant security or normative change they authored.

## Evolution

The governance model may move to multiple maintainers or a technical steering group when sustained external contribution justifies it. Such a change requires a documented RFC.
