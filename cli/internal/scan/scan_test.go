package scan

import (
	"os"
	"path/filepath"
	"testing"
)

func writeSkill(t *testing.T, root, name, body string) string {
	t.Helper()
	folder := filepath.Join(root, name)
	if err := os.MkdirAll(folder, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(folder, MainFileName), []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	return folder
}

func TestSlugify(t *testing.T) {
	cases := map[string]string{
		"Code Review":         "code_review",
		"  Trim Whitespace  ": "trim_whitespace",
		"!!!":                 "skill",
		"hello-world":         "hello_world",
	}
	for in, want := range cases {
		if got := Slugify(in); got != want {
			t.Errorf("Slugify(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestDiscoverParsesFrontmatter(t *testing.T) {
	root := t.TempDir()
	writeSkill(t, root, "code-review",
		"---\nname: Code Review\ndescription: review code\n---\nBody.\n")
	writeSkill(t, root, "trim",
		"# Just a header\n\nFirst paragraph here.\n\nSecond paragraph.\n")

	out, err := Discover([]Source{{Path: root, Label: "test"}})
	if err != nil {
		t.Fatal(err)
	}
	if len(out) != 2 {
		t.Fatalf("expected 2 skills, got %d (%+v)", len(out), out)
	}
	bySlug := map[string]Skill{}
	for _, s := range out {
		bySlug[s.Slug] = s
	}
	cr, ok := bySlug["code_review"]
	if !ok {
		t.Fatalf("missing code_review; got %v", bySlug)
	}
	if cr.Name != "Code Review" || cr.Description != "review code" {
		t.Fatalf("wrong frontmatter parse: %+v", cr)
	}
	tr := bySlug["trim"]
	if tr.Description != "First paragraph here." {
		t.Fatalf("description fallback wrong: %q", tr.Description)
	}
}

func TestDiscoverSourcesScansDotDirs(t *testing.T) {
	home := t.TempDir()
	cwd := t.TempDir()
	if err := os.MkdirAll(filepath.Join(home, ".claude", "skills"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(cwd, ".agents", "skills"), 0o755); err != nil {
		t.Fatal(err)
	}
	sources := DiscoverSources(home, cwd, nil, []string{".claude", ".agents"})
	if len(sources) != 2 {
		t.Fatalf("expected 2 sources, got %d (%+v)", len(sources), sources)
	}
}

func TestDedupeAgainstFiltersByRemoteSlugs(t *testing.T) {
	local := []Skill{
		{Slug: "alpha"},
		{Slug: "beta"},
		{Slug: "gamma"},
	}
	remote := map[string]struct{}{"beta": {}}
	out := DedupeAgainst(local, remote)
	if len(out) != 2 || out[0].Slug != "alpha" || out[1].Slug != "gamma" {
		t.Fatalf("dedupe wrong: %+v", out)
	}
}

func TestHashIsDeterministic(t *testing.T) {
	root := t.TempDir()
	folder := writeSkill(t, root, "alpha", "hello")
	s := Skill{Folder: folder}
	h1, err := s.Hash()
	if err != nil {
		t.Fatal(err)
	}
	h2, err := s.Hash()
	if err != nil {
		t.Fatal(err)
	}
	if h1 != h2 || h1 == "" {
		t.Fatalf("non-deterministic hash: %q vs %q", h1, h2)
	}
}
