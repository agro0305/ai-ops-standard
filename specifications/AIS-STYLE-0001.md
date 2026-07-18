---
document_id: AIS-STYLE-0001
title: AI-OPS Document Style Guide
status: Draft
version: 0.2.0
language: en
canonical: true
authors:
  - AI-OPS Project
created: 2026-07-19
updated: 2026-07-19
supersedes: null
superseded_by: null
---

# AIS-STYLE-0001 — AI-OPS Document Style Guide

## 1. Purpose

This document defines the mandatory structure, metadata, terminology, normative language, versioning rules and editorial conventions for AI-OPS specifications, RFCs, schemas, reference implementations and compliance documents.

Its purpose is to ensure that every AI-OPS document is consistent, testable, reviewable and suitable for long-term maintenance.

## 2. Scope

This guide applies to:

- AIS specifications;
- AI-OPS RFC documents;
- machine-readable schemas;
- reference implementation documentation;
- compliance test documentation;
- dashboard and API documentation;
- official translations.

It does not define the technical behavior of AI agents. Technical behavior is defined by individual AIS specifications.

## 3. Normative language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY** and **OPTIONAL** are normative when written in uppercase.

Lowercase forms are descriptive and non-normative.

Each normative requirement MUST be:

- unambiguous;
- independently testable;
- attributable to one document;
- assigned a stable requirement identifier.

Requirement identifiers MUST use this form:

```text
AIS-<document-number>-REQ-<three-digit-number>
```

Example:

```text
AIS-0003-REQ-001
```

A requirement identifier MUST NOT be reused for a different requirement after publication.

## 4. Document identifiers

### 4.1 AIS specifications

Normative specifications use:

```text
AIS-NNNN
```

Example:

```text
AIS-0003
```

### 4.2 Style documents

Style and governance documents use:

```text
AIS-STYLE-NNNN
```

### 4.3 RFC documents

Proposals not yet accepted into the standard use:

```text
RFC-NNNN
```

### 4.4 Schemas

Machine-readable schema filenames SHOULD describe their object and version.

Example:

```text
operation-report.schema.json
```

## 5. Required metadata

Every canonical AIS document MUST include YAML front matter containing:

```yaml
document_id:
title:
status:
version:
language:
canonical:
authors:
created:
updated:
supersedes:
superseded_by:
```

### 5.1 Metadata rules

- `document_id` MUST match the filename.
- `version` MUST follow semantic versioning.
- `language` MUST use a short language code.
- canonical English documents MUST use `canonical: true`.
- translations MUST use `canonical: false`.
- `created` and `updated` MUST use `YYYY-MM-DD`.
- unknown values MAY be represented as `null`.

## 6. Document status

Allowed status values are:

- `Draft` — incomplete and unstable;
- `Review` — complete enough for formal review;
- `Accepted` — approved as part of the standard;
- `Deprecated` — still available but no longer recommended;
- `Superseded` — replaced by another document;
- `Withdrawn` — removed before acceptance.

A document MUST NOT move directly from `Draft` to `Accepted` without a review stage.

## 7. Canonical language and translations

English is the canonical language of AI-OPS.

Official Serbian translations MUST:

- use the suffix `.sr.md`;
- reference the canonical document;
- preserve requirement identifiers;
- preserve normative meaning;
- preserve section numbering where practical;
- not introduce new requirements;
- state that the English document is canonical.

If a translation conflicts with the canonical document, the canonical English document takes precedence.

## 8. Required document structure

A normative AIS specification SHOULD contain the following sections when applicable:

1. Purpose
2. Scope
3. Terminology
4. Context and problem statement
5. Requirements
6. Data model
7. Process model
8. Security considerations
9. Privacy considerations
10. Failure handling
11. Rollback requirements
12. Examples
13. Compliance
14. References
15. Revision history

Sections that are not applicable MAY be omitted, but the omission SHOULD be evident from context.

## 9. Requirement writing rules

A normative requirement MUST state:

- the responsible actor;
- the required or prohibited behavior;
- the condition under which it applies;
- an observable result.

Good example:

> **AIS-0005-REQ-001:** Before modifying an existing configuration file, an agent MUST create a recoverable backup and record its location in the operation report.

Bad example:

> Agents should probably make backups when needed.

Requirements MUST NOT depend on undocumented assumptions.

Requirements SHOULD avoid combining unrelated behaviors in one statement.

## 10. Normative and non-normative content

Normative sections define required behavior.

Examples, rationale, implementation notes and diagrams are non-normative unless explicitly marked otherwise.

The following labels SHOULD be used:

- `Normative requirement`
- `Non-normative example`
- `Implementation note`
- `Rationale`

## 11. Code and command examples

Code and command examples MUST specify a language or format where possible.

Examples that modify system state MUST clearly state that they are examples.

Commands MUST NOT expose real secrets, tokens or private keys.

Placeholders SHOULD use descriptive uppercase names:

```text
LAN_CIDR
SERVICE_PORT
CONFIG_FILE
BACKUP_PATH
```

Commands SHOULD be idempotent or explicitly document when they are not.

## 12. Diagrams

ASCII diagrams MAY be used for simple flows.

Mermaid SHOULD be used for machine-readable diagrams when supported.

A diagram MUST NOT be the only representation of a normative requirement.

## 13. Tables

Tables SHOULD be used for:

- status definitions;
- requirement mappings;
- capability matrices;
- compliance results;
- version history.

Large procedures SHOULD NOT be compressed into tables when sequential text is clearer.

## 14. File naming

Canonical specification:

```text
AIS-0003.md
```

Serbian translation:

```text
AIS-0003.sr.md
```

RFC:

```text
RFC-0001.md
```

Schema:

```text
operation-report.schema.json
```

Filenames MUST use ASCII characters, hyphens and lowercase extensions.

## 15. Versioning

Each document uses semantic versioning:

- MAJOR — incompatible normative change;
- MINOR — backward-compatible normative addition;
- PATCH — clarification, typo fix or editorial improvement with no behavioral change.

Draft documents MAY change rapidly but MUST still maintain a revision history.

## 16. Change control

Every change to an accepted specification MUST include:

- rationale;
- affected requirement identifiers;
- compatibility impact;
- compliance impact;
- migration guidance when needed.

A breaking change SHOULD be proposed through an RFC before modifying an accepted AIS specification.

## 17. Cross-references

Documents MUST reference other specifications using stable document IDs.

Preferred form:

```text
AIS-0005
AIS-0005-REQ-001
```

Links MAY be added, but the identifier MUST remain readable without the link.

## 18. Security and secret handling

Documents and examples MUST NOT contain:

- real API keys;
- passwords;
- private tokens;
- private SSH keys;
- production certificates;
- unredacted personal data.

Examples MUST use placeholders or redacted values.

## 19. Compliance mapping

Every testable normative requirement SHOULD map to one or more compliance tests.

Recommended mapping format:

```yaml
requirement: AIS-0005-REQ-001
tests:
  - compliance/tests/test_backup_before_change.py
```

A requirement that cannot be tested automatically MUST define a manual verification procedure.

## 20. Revision history

| Version | Date | Status | Description |
|---|---|---|---|
| 0.1.0 | 2026-07-19 | Draft | Initial skeleton |
| 0.2.0 | 2026-07-19 | Draft | Expanded document structure, metadata, requirements and translation rules |
