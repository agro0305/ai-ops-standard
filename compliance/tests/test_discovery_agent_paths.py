from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "implementations" / "discovery" / "aiops_discovery.py"
SPEC = importlib.util.spec_from_file_location("aiops_discovery_paths", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def make_executable(path: Path, output: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{output}'\n", encoding="utf-8")
    path.chmod(0o755)


def test_resolves_user_installed_agents_outside_service_path(tmp_path, monkeypatch):
    kimi = tmp_path / ".kimi-code" / "bin" / "kimi"
    node_bin = tmp_path / ".nvm" / "versions" / "node" / "v22.22.3" / "bin"
    claude = node_bin / "claude"
    codex = node_bin / "codex"
    opencode = node_bin / "opencode"

    make_executable(kimi, "kimi 0.19.1")
    make_executable(claude, "claude 1.0.0")
    make_executable(codex, "codex 1.0.0")
    make_executable(opencode, "opencode 1.0.0")

    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr(MODULE, "candidate_homes", lambda: [tmp_path])

    results = MODULE.versions(
        {
            "kimi": ["kimi", "-V"],
            "claude": ["claude", "--version"],
            "codex": ["codex", "--version"],
            "opencode": ["opencode", "--version"],
        }
    )

    assert all(results[name]["available"] for name in results)
    assert results["kimi"]["resolved_path"] == str(kimi)
    assert results["claude"]["resolved_path"] == str(claude)
    assert results["codex"]["resolved_path"] == str(codex)
    assert results["opencode"]["resolved_path"] == str(opencode)
    assert results["kimi"]["stdout"] == "kimi 0.19.1"


def test_candidate_paths_include_common_cli_install_locations(tmp_path, monkeypatch):
    nvm_bin = tmp_path / ".nvm" / "versions" / "node" / "v22.22.3" / "bin"
    for path in (
        tmp_path / ".local" / "bin",
        tmp_path / ".kimi-code" / "bin",
        tmp_path / ".npm-global" / "bin",
        nvm_bin,
    ):
        path.mkdir(parents=True)

    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr(MODULE, "candidate_homes", lambda: [tmp_path])

    paths = set(MODULE.candidate_search_paths())
    assert tmp_path / ".local" / "bin" in paths
    assert tmp_path / ".kimi-code" / "bin" in paths
    assert tmp_path / ".npm-global" / "bin" in paths
    assert nvm_bin in paths
