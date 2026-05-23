"""Shared SKILL.md frontmatter helpers.

Used by :mod:`skills_mcp.registry_api` when summarizing registry entries.
The parser is intentionally minimal (flat ``key: value`` only) so we avoid
adding PyYAML as a runtime dependency.
"""

from __future__ import annotations


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
	"""Extract a flat YAML-ish frontmatter block (``--- ... ---``) from the top of a file.

	Multi-line values, lists, and nested keys are not supported and will be
	silently dropped — this matches the constraint documented in the Go
	scanner's frontmatter helper.
	"""
	if not text.startswith("---"):
		return {}, text
	lines = text.splitlines()
	end = None
	for i in range(1, len(lines)):
		if lines[i].strip() == "---":
			end = i
			break
	if end is None:
		return {}, text
	meta: dict[str, str] = {}
	for raw in lines[1:end]:
		if ":" in raw and not raw.lstrip().startswith("#"):
			k, v = raw.split(":", 1)
			meta[k.strip()] = v.strip().strip('"').strip("'")
	body = "\n".join(lines[end + 1 :]).lstrip("\n")
	return meta, body


def first_paragraph(text: str, limit: int = 240) -> str:
	"""Return the first non-heading paragraph (≤ ``limit`` chars).

	Used as a description fallback when a SKILL.md has no ``description:``
	frontmatter key.
	"""
	for block in text.split("\n\n"):
		cleaned = " ".join(block.strip().split())
		if cleaned and not cleaned.startswith("#"):
			return cleaned[:limit]
	return text.strip()[:limit]
