#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = ROOT / "specifications"
SCHEMA_DIR = ROOT / "schemas"

REQUIRED_META = {
    "document_id",
    "title",
    "status",
    "version",
    "language",
    "canonical",
    "created",
}


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


def main() -> int:
    errors: list[str] = []

    for path in sorted(SPEC_DIR.glob("AIS-*.md")):
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
            errors.append(f"{path}: document_id {doc_id!r} does not match {expected!r}")

        version = meta.get("version", "")
        if not re.fullmatch(r"\d+\.\d+\.\d+", version):
            errors.append(f"{path}: invalid semantic version {version!r}")

        if path.name.endswith(".sr.md") and meta.get("canonical") != "false":
            errors.append(f"{path}: Serbian translation must be non-canonical")

    for path in sorted(SCHEMA_DIR.glob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{path}: invalid JSON: {exc}")

    if errors:
        print("Repository validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Repository validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
