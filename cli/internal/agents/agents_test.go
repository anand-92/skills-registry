package agents

import (
	"strings"
	"testing"
)

func TestAllReturnsCuratedList(t *testing.T) {
	all := All()
	if len(all) < 20 {
		t.Fatalf("expected a sizeable curated list, got %d", len(all))
	}
	// Every entry has both a DotDir and a Display.
	for _, target := range all {
		if target.DotDir == "" {
			t.Fatalf("empty DotDir for %+v", target)
		}
		if target.Display == "" {
			t.Fatalf("empty Display for %+v", target)
		}
		if !strings.HasPrefix(target.DotDir, ".") {
			t.Fatalf("DotDir should start with a dot: %q", target.DotDir)
		}
	}
}

func TestUniversalAppearsFirst(t *testing.T) {
	all := All()
	if !all[0].Universal {
		t.Fatalf("expected universal entry first; got %+v", all[0])
	}
	for _, target := range all[1:] {
		if target.Universal {
			t.Fatalf("multiple universal entries; only one expected: %+v", target)
		}
	}
}

func TestSkillsDirRoutes(t *testing.T) {
	u := Target{DotDir: ".claude", UnderHome: true}
	if u.SkillsDir("/home/me", "/cwd") != "/home/me/.claude/skills" {
		t.Fatalf("home-rooted SkillsDir wrong")
	}
	p := Target{DotDir: ".agents", UnderHome: false}
	if p.SkillsDir("/home/me", "/cwd") != "/cwd/.agents/skills" {
		t.Fatalf("project-local SkillsDir wrong")
	}
}
