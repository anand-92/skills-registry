"""Tests for ``skills_mcp.init`` (the thin bootstrap shim)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from skills_mcp import init


@pytest.fixture
def stub_gh(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(init, "ensure_authed", lambda: Path("/fake/gh"))


def _make_args(**overrides: Any) -> Any:
	import argparse

	defaults = {
		"skip_download": True,
		"repo": None,
		"visibility": None,
		"no_agents": False,
	}
	defaults.update(overrides)
	return argparse.Namespace(**defaults)


def test_cmd_init_aborts_when_gh_missing(
	monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
	def raise_missing() -> Path:
		raise init.GhNotFoundError("install gh first")

	monkeypatch.setattr(init, "ensure_authed", raise_missing)
	rc = init.cmd_init(_make_args())
	assert rc == 3
	assert "install gh first" in capsys.readouterr().err


def test_cmd_init_aborts_when_unauthed(
	monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
	def raise_unauthed() -> Path:
		raise init.GhNotAuthedError("run gh auth login")

	monkeypatch.setattr(init, "ensure_authed", raise_unauthed)
	rc = init.cmd_init(_make_args())
	assert rc == 4
	assert "gh auth login" in capsys.readouterr().err


def test_cmd_init_skip_download_requires_existing_binary(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	stub_gh: None,
	capsys: pytest.CaptureFixture[str],
) -> None:
	monkeypatch.setenv("SKILLS_BIN_DIR", str(tmp_path))
	rc = init.cmd_init(_make_args(skip_download=True))
	assert rc == 1
	assert "skip-download" in capsys.readouterr().err


def test_cmd_init_execs_into_go_binary(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	stub_gh: None,
) -> None:
	monkeypatch.setenv("SKILLS_BIN_DIR", str(tmp_path))
	binary = tmp_path / init.BINARY_NAME
	binary.write_text("#!/bin/sh\nexit 0\n")
	binary.chmod(0o755)

	calls: list[list[str]] = []

	def fake_execv(path: str, args: list[str]) -> None:
		calls.append([path, *args])

	monkeypatch.setattr(init.os, "execv", fake_execv)
	rc = init.cmd_init(_make_args(skip_download=True))
	assert rc == 0
	assert len(calls) == 1
	assert calls[0][0] == str(binary)
	assert "bootstrap" in calls[0]


def test_cmd_init_passes_flags_to_binary(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	stub_gh: None,
) -> None:
	monkeypatch.setenv("SKILLS_BIN_DIR", str(tmp_path))
	binary = tmp_path / init.BINARY_NAME
	binary.write_text("#!/bin/sh\nexit 0\n")
	binary.chmod(0o755)

	calls: list[list[str]] = []
	monkeypatch.setattr(init.os, "execv", lambda p, a: calls.append([p, *a]))

	init.cmd_init(
		_make_args(
			skip_download=True,
			repo="alice/skills",
			visibility="private",
			no_agents=True,
		)
	)
	assert calls
	argv = calls[0]
	assert "--repo" in argv and "alice/skills" in argv
	assert "--visibility" in argv and "private" in argv
	assert "--no-agents" in argv


def test_install_dir_respects_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	monkeypatch.setenv("SKILLS_BIN_DIR", str(tmp_path / "custom"))
	assert init._install_dir() == (tmp_path / "custom").resolve()


def test_install_dir_default(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.delenv("SKILLS_BIN_DIR", raising=False)
	assert init._install_dir() == Path.home() / ".local" / "bin"


def test_platform_pattern_raises_on_unknown(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	monkeypatch.setattr(init.platform, "system", lambda: "Plan9")
	with pytest.raises(init.CliDownloadError, match="Unsupported platform"):
		init._platform_asset_pattern()


def test_platform_pattern_returns_known() -> None:
	# Whatever the actual host is, the tokens must be in our supported sets.
	os_token, arch_token = init._platform_asset_pattern()
	assert os_token in {"darwin", "linux", "windows"}
	assert arch_token in {"amd64", "arm64"}
