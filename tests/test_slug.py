"""Tests for ``skills_mcp.__main__._slug``."""

from __future__ import annotations

import pytest

from skills_mcp.__main__ import _slug


@pytest.mark.parametrize(
	("raw", "expected"),
	[
		("hello", "hello"),
		("Hello World", "hello_world"),
		("  Trim Me  ", "trim_me"),
		("MiXeD_CaSe", "mixed_case"),
		("multiple   spaces", "multiple_spaces"),
		("dots.and-dashes", "dots_and_dashes"),
		("foo/bar baz", "foo_bar_baz"),
		("unicode-éclair", "unicode_clair"),
		("123 numbers", "123_numbers"),
		("__leading_and_trailing__", "leading_and_trailing"),
	],
)
def test_slug_basic_cases(raw: str, expected: str) -> None:
	assert _slug(raw) == expected


def test_slug_empty_string_falls_back_to_default() -> None:
	assert _slug("") == "skill"


def test_slug_only_punctuation_falls_back_to_default() -> None:
	assert _slug("!!! ??? ---") == "skill"


def test_slug_only_whitespace_falls_back_to_default() -> None:
	assert _slug("   \t\n") == "skill"


def test_slug_idempotent_on_already_clean_input() -> None:
	clean = "already_clean_slug_123"
	assert _slug(clean) == clean
