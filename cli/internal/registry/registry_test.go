package registry

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// stubGH writes a small shell script that replays scripted JSON responses
// based on substring matches against argv. Each match is consumed in order.
//
// Tests load a JSON file in the form
//
//	[{"key": "GET repos/x/y/...", "body": <any>, "exit": 0}]
//
// where "body" can be a string (echoed verbatim) or any JSON value (re-encoded).
func stubGH(t *testing.T, entries []map[string]any) (string, string) {
	t.Helper()
	dir := t.TempDir()
	statePath := filepath.Join(dir, "state.json")
	raw, err := json.Marshal(entries)
	if err != nil {
		t.Fatalf("marshal stub entries: %v", err)
	}
	if err := os.WriteFile(statePath, raw, 0o644); err != nil {
		t.Fatalf("write state: %v", err)
	}
	script := fmt.Sprintf(`#!/bin/sh
state=%q
python3 - <<'PY' "$state" "$@"
import json, sys
state = sys.argv[1]
argv = " ".join(sys.argv[2:])
with open(state) as f:
    data = json.load(f)
for i, entry in enumerate(data):
    if entry["key"] in argv:
        body = entry.get("body", "")
        exit_code = entry.get("exit", 0)
        data.pop(i)
        with open(state, "w") as f:
            json.dump(data, f)
        if body:
            sys.stdout.write(body if isinstance(body, str) else json.dumps(body))
        sys.exit(exit_code)
sys.stderr.write(f"unexpected gh call: {argv}\n")
sys.exit(99)
PY
`, statePath)
	binary := filepath.Join(dir, "gh")
	if err := os.WriteFile(binary, []byte(script), 0o755); err != nil {
		t.Fatalf("write stub: %v", err)
	}
	return binary, statePath
}

func TestListReturnsSummaries(t *testing.T) {
	frontmatter := "---\nname: Code Review\ndescription: review code\n---\nBody.\n"
	encoded := base64.StdEncoding.EncodeToString([]byte(frontmatter))
	bin, _ := stubGH(t, []map[string]any{
		{
			"key": "GET repos/x/y/contents/",
			"body": []map[string]any{
				{"name": "code-review", "type": "dir", "sha": "tree-1"},
				{"name": "readme.md", "type": "file"},
				{"name": ".github", "type": "dir", "sha": "ignore"},
			},
		},
		{
			"key":  "GET repos/x/y/contents/code-review/SKILL.md",
			"body": map[string]any{"encoding": "base64", "content": encoded},
		},
	})
	c := &Client{GH: bin, Repo: "x/y", DefaultBranch: "main"}
	summaries, err := c.List(context.Background())
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(summaries) != 1 || summaries[0].Slug != "code-review" {
		t.Fatalf("unexpected summaries: %+v", summaries)
	}
	if summaries[0].Name != "Code Review" {
		t.Fatalf("expected name parsed from frontmatter; got %q", summaries[0].Name)
	}
}

func TestPublishRetriesOnConflict(t *testing.T) {
	makeRound := func(commitSHA string, conflict bool) []map[string]any {
		patchBody := map[string]any{"object": map[string]any{"sha": commitSHA}}
		exit := 0
		var bodyValue any = patchBody
		if conflict {
			bodyValue = "HTTP 422: non-fast-forward"
			exit = 1
		}
		return []map[string]any{
			{"key": "GET repos/x/y/git/ref/heads/main", "body": map[string]any{"object": map[string]any{"sha": "parent"}}},
			{"key": "GET repos/x/y/git/commits/parent", "body": map[string]any{"tree": map[string]any{"sha": "base"}}},
			{"key": "GET repos/x/y/git/trees/base?recursive=1", "body": map[string]any{"tree": []any{}}},
			{"key": "POST repos/x/y/git/blobs", "body": map[string]any{"sha": "blob"}},
			{"key": "POST repos/x/y/git/trees", "body": map[string]any{"sha": "tree"}},
			{"key": "POST repos/x/y/git/commits", "body": map[string]any{"sha": commitSHA}},
			{"key": "PATCH repos/x/y/git/refs/heads/main", "body": bodyValue, "exit": exit},
		}
	}
	entries := append(makeRound("c1", true), makeRound("c2", false)...)
	bin, _ := stubGH(t, entries)
	c := &Client{GH: bin, Repo: "x/y", DefaultBranch: "main", MaxRetries: 3, RetryBaseS: 0}
	start := time.Now()
	sha, err := c.Publish(context.Background(), "code-review", map[string][]byte{"SKILL.md": []byte("hi")}, "")
	if err != nil {
		t.Fatalf("Publish: %v", err)
	}
	if sha != "c2" {
		t.Fatalf("expected c2, got %q", sha)
	}
	if time.Since(start) > 5*time.Second {
		t.Fatalf("retry should be quick when RetryBaseS=0")
	}
}

func TestGetDownloadsRecursively(t *testing.T) {
	mdContent := base64.StdEncoding.EncodeToString([]byte("# SKILL"))
	extraContent := base64.StdEncoding.EncodeToString([]byte("data"))
	bin, _ := stubGH(t, []map[string]any{
		{
			"key": "GET repos/x/y/contents/code-review",
			"body": []map[string]any{
				{"name": "SKILL.md", "type": "file"},
				{"name": "resources", "type": "dir"},
			},
		},
		{
			"key":  "GET repos/x/y/contents/code-review/SKILL.md",
			"body": map[string]any{"encoding": "base64", "content": mdContent},
		},
		{
			"key": "GET repos/x/y/contents/code-review/resources",
			"body": []map[string]any{
				{"name": "extra.md", "type": "file"},
			},
		},
		{
			"key":  "GET repos/x/y/contents/code-review/resources/extra.md",
			"body": map[string]any{"encoding": "base64", "content": extraContent},
		},
	})
	c := &Client{GH: bin, Repo: "x/y", DefaultBranch: "main"}
	dest := t.TempDir()
	if err := c.Get(context.Background(), "code-review", dest); err != nil {
		t.Fatalf("Get: %v", err)
	}
	got, err := os.ReadFile(filepath.Join(dest, "SKILL.md"))
	if err != nil || string(got) != "# SKILL" {
		t.Fatalf("SKILL.md missing or wrong content: %q %v", got, err)
	}
	extra, err := os.ReadFile(filepath.Join(dest, "resources", "extra.md"))
	if err != nil || string(extra) != "data" {
		t.Fatalf("resources/extra.md missing: %q %v", extra, err)
	}
}
