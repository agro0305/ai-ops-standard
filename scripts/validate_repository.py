#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = ROOT / "specifications"
SCHEMA_DIR = ROOT / "schemas"
VERSION_FILE = ROOT / "VERSION"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"
INSTALLATION_FILE = ROOT / "docs" / "INSTALLATION.md"

REQUIRED_META = {
    "document_id",
    "title",
    "status",
    "version",
    "language",
    "canonical",
    "created",
}
SEMVER = re.compile(r"\d+\.\d+\.\d+")


def parse_front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing YAML front matter")
    _, block, _ = text.split("---", 2)
    result: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
    return result


def validate_release_files(errors: list[str]) -> str | None:
    if not VERSION_FILE.is_file():
        errors.append(f"{VERSION_FILE}: missing VERSION file")
        return None
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not SEMVER.fullmatch(version):
        errors.append(f"{VERSION_FILE}: invalid semantic version {version!r}")
        return None

    for required in (CHANGELOG_FILE, INSTALLATION_FILE):
        if not required.is_file():
            errors.append(f"{required}: required release file is missing")

    if CHANGELOG_FILE.is_file():
        changelog = CHANGELOG_FILE.read_text(encoding="utf-8")
        if f"## {version}" not in changelog:
            errors.append(
                f"{CHANGELOG_FILE}: no changelog section for project version {version}"
            )
    return version


def main() -> int:
    errors: list[str] = []
    validate_release_files(errors)

    specifications = sorted(SPEC_DIR.glob("AIS-*.md"))
    if not specifications:
        errors.append(f"{SPEC_DIR}: no specifications found")
    for path in specifications:
        try:
            meta = parse_front_matter(path)
        except Exception as exc:
            errors.append(f"{path}: {exc}")
            continue

        missing = REQUIRED_META - meta.keys()
        if missing:
            errors.append(f"{path}: missing metadata {sorted(missing)}")

        doc_id = meta.get("document_id", "")
        expected = path.name.removesuffix(".sr.md").removesuffix(".md")
        if doc_id != expected:
            errors.append(
                f"{path}: document_id {doc_id!r} does not match {expected!r}"
            )

        version = meta.get("version", "")
        if not SEMVER.fullmatch(version):
            errors.append(f"{path}: invalid semantic version {version!r}")

        if path.name.endswith(".sr.md") and meta.get("canonical") != "false":
            errors.append(f"{path}: Serbian translation must be non-canonical")

    schemas = sorted(SCHEMA_DIR.glob("*.json"))
    if not schemas:
        errors.append(f"{SCHEMA_DIR}: no schemas found")
    schema_ids: set[str] = set()
    for path in schemas:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{path}: invalid JSON: {exc}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{path}: schema root must be an object")
            continue
        schema_id = payload.get("$id")
        if not isinstance(schema_id, str) or not schema_id:
            errors.append(f"{path}: schema must define a non-empty $id")
        elif schema_id in schema_ids:
            errors.append(f"{path}: duplicate schema $id {schema_id!r}")
        else:
            schema_ids.add(schema_id)

    if errors:
        print("Repository validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Repository validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
