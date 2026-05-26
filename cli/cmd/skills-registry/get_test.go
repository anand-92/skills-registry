package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/anand-92/skills-registry/cli/internal/cache"
)

func TestResolveDest(t *testing.T) {
	t.Run("empty dest uses default parent", func(t *testing.T) {
		// Production callers pass cache.CacheRoot() as the default parent
		// (issue #29: skills must land under ~/.cache/skills-mcp/skills/,
		// not the cwd-relative .agents/skills tree the old code produced).
		parent := t.TempDir()
		got, reused := resolveDest("agp-9-upgrade", "", parent)
		want := filepath.Join(parent, "agp_9_upgrade")
		if got != want {
			t.Fatalf("dest = %q, want %q", got, want)
		}
		if reused != "" {
			t.Fatalf("reused = %q, want empty", reused)
		}
	})

	t.Run("empty dest in production uses cache.CacheRoot()", func(t *testing.T) {
		// Regression guard for issue #29: DownloadSkill resolves its
		// default parent to cache.CacheRoot(), so an empty --dest must
		// produce a path rooted at the global cache (~/.cache/skills-mcp/
		// skills) — never the cwd's .agents/ directory.
		t.Setenv("XDG_CACHE_HOME", "")
		home := t.TempDir()
		t.Setenv("HOME", home)
		got, _ := resolveDest("agp-9-upgrade", "", cache.CacheRoot())
		want := filepath.Join(home, ".cache", "skills-mcp", "skills", "agp_9_upgrade")
		if got != want {
			t.Fatalf("dest = %q, want %q", got, want)
		}
		// And the path explicitly does NOT live in cwd/.agents (issue #29).
		cwd, _ := os.Getwd()
		stray := filepath.Join(cwd, ".agents") + string(filepath.Separator)
		if strings.HasPrefix(got, stray) {
			t.Fatalf("dest %q must not live under %q", got, stray)
		}
	})

	t.Run("empty dest honors XDG_CACHE_HOME", func(t *testing.T) {
		// cache.CacheRoot() respects XDG_CACHE_HOME, so callers using it
		// as the default parent automatically inherit that override. This
		// pins the behaviour for users (and CI runners) that move the
		// cache off the default ~/.cache location.
		xdg := t.TempDir()
		t.Setenv("XDG_CACHE_HOME", xdg)
		got, _ := resolveDest("agp_9_upgrade", "", cache.CacheRoot())
		want := filepath.Join(xdg, "skills-mcp", "skills", "agp_9_upgrade")
		if got != want {
			t.Fatalf("dest = %q, want %q", got, want)
		}
	})

	t.Run("matching basename used as-is", func(t *testing.T) {
		tmp := t.TempDir()
		explicit := filepath.Join(tmp, "agp_9_upgrade")
		got, reused := resolveDest("agp_9_upgrade", explicit, tmp)
		if got != explicit {
			t.Fatalf("dest = %q, want %q", got, explicit)
		}
		if reused != "" {
			t.Fatalf("reused = %q, want empty", reused)
		}
	})

	t.Run("hyphenated basename slugifies to same canonical slug", func(t *testing.T) {
		tmp := t.TempDir()
		// The user typed the hyphenated form; basename slugifies to the
		// same canon, so we honor the user's literal path (no rewriting).
		explicit := filepath.Join(tmp, "agp-9-upgrade")
		got, reused := resolveDest("agp_9_upgrade", explicit, tmp)
		if got != explicit {
			t.Fatalf("dest = %q, want %q", got, explicit)
		}
		if reused != "" {
			t.Fatalf("reused = %q, want empty", reused)
		}
	})

	t.Run("dest treated as parent when basename does not match", func(t *testing.T) {
		tmp := t.TempDir()
		got, reused := resolveDest("agp_9_upgrade", tmp, tmp)
		want := filepath.Join(tmp, "agp_9_upgrade")
		if got != want {
			t.Fatalf("dest = %q, want %q", got, want)
		}
		if reused != "" {
			t.Fatalf("reused = %q, want empty", reused)
		}
	})

	t.Run("reuses existing sibling with equivalent slug", func(t *testing.T) {
		// Simulates the original bug: ~/.factory/skills/agp-9-upgrade already
		// exists; user invokes `get agp_9_upgrade --dest .../agp_9_upgrade`.
		// We should reuse the existing folder instead of creating a duplicate.
		parent := t.TempDir()
		existing := filepath.Join(parent, "agp-9-upgrade")
		if err := os.MkdirAll(existing, 0o755); err != nil {
			t.Fatalf("setup: %v", err)
		}
		requested := filepath.Join(parent, "agp_9_upgrade")
		got, reused := resolveDest("agp_9_upgrade", requested, parent)
		if got != existing {
			t.Fatalf("dest = %q, want %q (the existing sibling)", got, existing)
		}
		if reused != existing {
			t.Fatalf("reused = %q, want %q", reused, existing)
		}
	})

	t.Run("no false-positive when sibling already matches exactly", func(t *testing.T) {
		// If the folder we'd write to already exists, that's not a collision —
		// it's the happy "re-fetch the same skill" path. resolveDest should
		// return the same path with no reuse warning.
		parent := t.TempDir()
		final := filepath.Join(parent, "agp_9_upgrade")
		if err := os.MkdirAll(final, 0o755); err != nil {
			t.Fatalf("setup: %v", err)
		}
		got, reused := resolveDest("agp_9_upgrade", final, parent)
		if got != final {
			t.Fatalf("dest = %q, want %q", got, final)
		}
		if reused != "" {
			t.Fatalf("reused = %q, want empty (same path is not a collision)", reused)
		}
	})

	t.Run("parent-form dest also reuses existing sibling", func(t *testing.T) {
		// User passes a parent directory; the resolved path would be
		// parent/<slug>, but a slug-equivalent sibling already lives there.
		parent := t.TempDir()
		existing := filepath.Join(parent, "agp-9-upgrade")
		if err := os.MkdirAll(existing, 0o755); err != nil {
			t.Fatalf("setup: %v", err)
		}
		got, reused := resolveDest("agp_9_upgrade", parent, parent)
		if got != existing {
			t.Fatalf("dest = %q, want %q", got, existing)
		}
		if reused != existing {
			t.Fatalf("reused = %q, want %q", reused, existing)
		}
	})
}
