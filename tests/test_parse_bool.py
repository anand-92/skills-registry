"""Tests for ``skills_mcp.__main__._parse_bool``."""

from __future__ import annotations

import pytest

from skills_mcp.__main__ import _parse_bool


def test_missing_env_returns_default_true(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.delenv("SKILLS_TEST_BOOL", raising=False)
	assert _parse_bool("SKILLS_TEST_BOOL", True) is True


def test_missing_env_returns_default_false(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.delenv("SKILLS_TEST_BOOL", raising=False)
	assert _parse_bool("SKILLS_TEST_BOOL", False) is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "True", "yes", "YES", "on", "ON"])
def test_truthy_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
	monkeypatch.setenv("SKILLS_TEST_BOOL", value)
	assert _parse_bool("SKILLS_TEST_BOOL", False) is True


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "False", "no", "NO", "off", "OFF"])
def test_falsy_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
	monkeypatch.setenv("SKILLS_TEST_BOOL", value)
	assert _parse_bool("SKILLS_TEST_BOOL", True) is False


def test_whitespace_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setenv("SKILLS_TEST_BOOL", "  yes  ")
	assert _parse_bool("SKILLS_TEST_BOOL", False) is True


def test_invalid_value_raises_systemexit(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setenv("SKILLS_TEST_BOOL", "maybe")
	with pytest.raises(SystemExit) as excinfo:
		_parse_bool("SKILLS_TEST_BOOL", True)
	assert "SKILLS_TEST_BOOL" in str(excinfo.value)
	assert "maybe" in str(excinfo.value)


def test_empty_string_raises_systemexit(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setenv("SKILLS_TEST_BOOL", "")
	with pytest.raises(SystemExit):
		_parse_bool("SKILLS_TEST_BOOL", True)
