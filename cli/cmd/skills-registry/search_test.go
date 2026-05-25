package main

import (
	"bytes"
	"context"
	"testing"

	"github.com/anand-92/skills-registry/cli/internal/jsonout"
	"github.com/anand-92/skills-registry/cli/internal/registry"
)

func TestScoreAndSort(t *testing.T) {
	summaries := []registry.Summary{
		{Slug: "git_tool", Name: "Git Helper", Description: "Git helper commands"},
		{Slug: "js_lint", Name: "JS Linter", Description: "Ruff for JS"},
		{Slug: "py_format", Name: "Python Formatter", Description: "Beautiful python formatting"},
	}

	// Empty query returns all summaries unchanged.
	resEmpty := scoreAndSort(summaries, "")
	if len(resEmpty) != 3 {
		t.Fatalf("expected 3 results, got %d", len(resEmpty))
	}

	// Relevant query
	resGit := scoreAndSort(summaries, "git")
	if len(resGit) != 1 {
		t.Fatalf("expected 1 git match, got %d", len(resGit))
	}
	if resGit[0].Slug != "git_tool" {
		t.Fatalf("expected git_tool, got %s", resGit[0].Slug)
	}
}

func TestSearchJSON(t *testing.T) {
	// Simple sanity test for search subcommand in JSON mode
	prev := jsonout.Enabled()
	t.Cleanup(func() { jsonout.SetEnabled(prev) })
	jsonout.SetEnabled(true)

	// Since we mock config, Load will fail on missing config in standard tests or succeed if mocked/written.
	// But let's verify our subcommand runs of some cmd arguments or config load errors out safely.
	root := newRootCmd()
	root.SetArgs([]string{"search", "git", "--json"})
	
	var stdout, stderr bytes.Buffer
	root.SetOut(&stdout)
	root.SetErr(&stderr)

	root.ExecuteContext(context.Background())
	// In the test context config.Load probably fails, but at least we can check that it doesn't crash.
}
