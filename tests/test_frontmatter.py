"""Tests for ``skills_mcp.frontmatter.parse_frontmatter``."""

from __future__ import annotations

from skills_mcp.frontmatter import parse_frontmatter


def test_no_frontmatter_returns_full_text_and_empty_meta() -> None:
	text = "# Just a heading\n\nSome body text."
	meta, body = parse_frontmatter(text)
	assert meta == {}
	assert body == text


def test_simple_frontmatter_is_parsed() -> None:
	text = "---\nname: My Skill\ndescription: Does something useful\n---\nBody here.\n"
	meta, body = parse_frontmatter(text)
	assert meta == {"name": "My Skill", "description": "Does something useful"}
	# splitlines() drops the trailing newline, so body has no trailing \n either.
	assert body == "Body here."


def test_quoted_values_are_stripped() -> None:
	text = "---\nname: \"Quoted Name\"\ndescription: 'single quoted'\n---\nrest\n"
	meta, _ = parse_frontmatter(text)
	assert meta["name"] == "Quoted Name"
	assert meta["description"] == "single quoted"


def test_comments_are_ignored() -> None:
	text = "---\n# a comment\nname: keep\n  # indented comment\n---\nbody\n"
	meta, _ = parse_frontmatter(text)
	assert meta == {"name": "keep"}


def test_lines_without_colon_are_skipped() -> None:
	text = "---\nname: only-this\nthis line has no colon\n---\nbody"
	meta, _ = parse_frontmatter(text)
	assert meta == {"name": "only-this"}


def test_unterminated_frontmatter_returns_full_text() -> None:
	text = "---\nname: Whoops\nno-closing-marker here\nstill no marker\n"
	meta, body = parse_frontmatter(text)
	assert meta == {}
	assert body == text


def test_value_with_internal_colon_is_preserved() -> None:
	text = "---\nurl: https://example.com/path:thing\n---\nbody"
	meta, _ = parse_frontmatter(text)
	assert meta["url"] == "https://example.com/path:thing"


def test_body_leading_blank_lines_are_stripped() -> None:
	text = "---\nname: x\n---\n\n\nhello\n"
	_, body = parse_frontmatter(text)
	assert body == "hello"


def test_only_frontmatter_no_body() -> None:
	text = "---\nname: only\n---\n"
	meta, body = parse_frontmatter(text)
	assert meta == {"name": "only"}
	assert body == ""


def test_empty_string_input() -> None:
	meta, body = parse_frontmatter("")
	assert meta == {}
	assert body == ""
