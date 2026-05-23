package main

import (
	"context"
	"fmt"
	"os"
	"strings"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/anand-92/skills-registry/cli/internal/config"
	"github.com/anand-92/skills-registry/cli/internal/registry"
	"github.com/anand-92/skills-registry/cli/internal/scan"
	"github.com/anand-92/skills-registry/cli/internal/tui"
)

// runWizard launches the onboarding wizard in alt-screen mode.
//
// F2.2 wires the first four steps (scan, repo name, visibility, push)
// directly into the wizard model via WizardDeps. F2.3 will inline the
// remaining steps (agent install, cleanup, MCP wire-up, done) — until
// then, runWizard falls through to runBootstrap for those steps. The
// fall-through is safe: bootstrap re-scans and re-checks the registry
// state, so a wizard-driven setup that's persisted its config is
// treated as a no-op create + push.
func runWizard(ctx context.Context) error {
	gh, err := registry.FindGH()
	if err != nil {
		return err
	}
	if err := registry.EnsureAuthed(ctx, gh); err != nil {
		return err
	}
	// Fail-fast before the wizard renders if the bulk push won't be
	// possible. The Go bootstrap path uses a single `git push` to avoid
	// GitHub's secondary rate limit; without `git` we'd lose 30+ steps
	// of context to a late failure.
	if err := requireGitForBootstrap(); err != nil {
		return err
	}

	deps := buildWizardDeps(gh)
	model := tui.NewWizard(ctx).WithDeps(deps)
	out, err := tea.NewProgram(
		model,
		tea.WithAltScreen(),
		tea.WithContext(ctx),
	).Run()
	if err != nil {
		return fmt.Errorf("run wizard: %w", err)
	}
	final, ok := out.(tui.WizardModel)
	if !ok {
		return fmt.Errorf("wizard returned unexpected model %T", out)
	}
	return finishWizard(ctx, final)
}

// finishWizard handles the post-wizard hand-off. Cancelled runs exit
// cleanly; successful runs fall through to bootstrap so steps 5-8 still
// happen until F2.3 lands them in the wizard itself.
func finishWizard(ctx context.Context, final tui.WizardModel) error {
	if final.Cancelled() {
		fmt.Println("Onboarding cancelled.")
		return nil
	}
	// F2.3 replaces this fall-through. Bootstrap sees the saved config
	// (write happened inside the push step) and skips its own create +
	// push, dropping the user straight into the agent multi-select.
	return runBootstrap(ctx, bootstrapOpts{})
}

// buildWizardDeps wires the real scan / create-repo / save-config /
// push callbacks. Each closure captures the resolved `gh` path and the
// caller's home + cwd so the wizard model doesn't need to know about any
// of that. The wizard's own ctx is threaded into each callback via the
// `c` parameter at call time.
func buildWizardDeps(gh string) tui.WizardDeps {
	home, _ := os.UserHomeDir()
	cwd, _ := os.Getwd()
	dotDirs := dotDirsFromAgents()
	return tui.WizardDeps{
		Scan: func(_ context.Context) ([]scan.Skill, error) {
			sources := scan.DiscoverSources(home, cwd, nil, dotDirs)
			return scan.Discover(sources)
		},
		CreateRepo: func(c context.Context, name, visibility string) (string, error) {
			return wizardCreateRepo(c, gh, name, visibility)
		},
		SaveConfig: func(repo string) error {
			_, err := config.Save(config.Config{Repo: repo, DefaultBranch: "main"})
			return err
		},
		Push: func(c context.Context, repo string, skills []scan.Skill,
			onProgress func(done, total int), onStatus func(msg string)) (int, error) {
			return wizardPushSkills(c, gh, repo, skills, onProgress, onStatus)
		},
	}
}

// wizardCreateRepo resolves the owner from the authenticated `gh` session
// and creates the repo (or reuses an existing one with the same name).
// Returns "owner/name" or an error. Mirrors the create-or-reuse path in
// runBootstrap so a half-completed onboarding can be safely re-run.
func wizardCreateRepo(ctx context.Context, gh, name, visibility string) (string, error) {
	owner, err := lookupGitHubOwner(ctx, gh)
	if err != nil {
		return "", err
	}
	full := name
	if !strings.Contains(name, "/") {
		full = owner + "/" + name
	}
	probe, err := registry.New(full, "main")
	if err != nil {
		return "", err
	}
	probe.GH = gh
	if exists, _ := probe.Exists(ctx); exists {
		// Reuse the existing repo. The follow-up push will fill in any
		// missing skills.
		return full, nil
	}
	description := "Personal skill registry — managed via skill-registry."
	created, err := probe.CreateRepo(ctx, name, visibility, description)
	if err != nil {
		// `gh repo create` says "already exists" when the owner has
		// previously created the same name; treat that as reuse.
		if strings.Contains(err.Error(), "already exists") {
			return full, nil
		}
		return "", err
	}
	if created == "" {
		created = full
	}
	return created, nil
}

// wizardPushSkills is the F2.2 push driver. It computes the delta against
// the remote registry, materializes every file, and runs PushTreeViaGit
// with the supplied progress / status callbacks plugged in. Returns the
// number of skills uploaded.
func wizardPushSkills(ctx context.Context, gh, repo string, skills []scan.Skill,
	onProgress func(done, total int), onStatus func(msg string)) (int, error) {
	client, err := registry.New(repo, "main")
	if err != nil {
		return 0, err
	}
	client.GH = gh
	missing, err := wizardPushMissing(ctx, client, skills, onStatus)
	if err != nil {
		return 0, err
	}
	if len(missing) == 0 {
		return 0, nil
	}
	files, err := wizardCollectFiles(missing)
	if err != nil {
		return 0, err
	}
	if onStatus != nil {
		onStatus(fmt.Sprintf("uploading %d skill(s) (%d files)…", len(missing), len(files)))
	}
	client.OnProgress = onProgress
	client.OnStatus = onStatus
	defer func() {
		client.OnProgress = nil
		client.OnStatus = nil
	}()
	commit := fmt.Sprintf("init: import %d skill(s)", len(missing))
	if err := client.PushTreeViaGit(ctx, files, commit); err != nil {
		return 0, err
	}
	return len(missing), nil
}

// wizardPushMissing returns the subset of `skills` that isn't already in
// the registry. Surfaces an "already in sync" status when the local set
// matches what's on GitHub.
func wizardPushMissing(ctx context.Context, client *registry.Client, skills []scan.Skill,
	onStatus func(msg string)) ([]scan.Skill, error) {
	existing, err := client.Slugs(ctx)
	if err != nil {
		// Brand-new repo with no commits yet returns a 404; treat that
		// as an empty registry rather than failing the whole push.
		existing = map[string]struct{}{}
	}
	missing := scan.DedupeAgainst(skills, existing)
	if len(missing) == 0 && onStatus != nil {
		onStatus("registry already in sync — nothing to upload.")
	}
	return missing, nil
}

// wizardCollectFiles materializes every file under each skill folder into
// a `<slug>/<rel>` keyed map, the format PushTreeViaGit expects.
func wizardCollectFiles(skills []scan.Skill) (map[string][]byte, error) {
	files := map[string][]byte{}
	for _, sk := range skills {
		if err := walkSkillIntoFiles(sk, files); err != nil {
			return nil, fmt.Errorf("read %s: %w", sk.Slug, err)
		}
	}
	return files, nil
}
