// skill-registry — TUI manager for a GitHub-backed skill registry.
package main

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

var version = "dev"

func main() {
	root := &cobra.Command{
		Use:   "skill-registry",
		Short: "Manage a GitHub-backed personal skill registry",
		Long: `skill-registry is a TUI for your personal skill registry repository.

Run "skill-registry bootstrap" once (or use the parent "skills-registry init"
wrapper) to create a registry repo and install the skill-registry doc
SKILL.md into your agent dot-folders.

Day-to-day, use:
  skill-registry list                     fuzzy-filterable list of every skill
  skill-registry get <slug>               download a skill to ./skill-registry/<slug>/
  skill-registry sync                     push local skills missing from the registry
  skill-registry add <source>             clone a source, multi-select what to publish
  skill-registry publish <path>           publish a single local skill folder`,
		Version: version,
	}

	root.AddCommand(
		newBootstrapCmd(),
		newListCmd(),
		newGetCmd(),
		newSyncCmd(),
		newAddCmd(),
		newPublishCmd(),
	)

	if err := root.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, "Error:", err)
		os.Exit(1)
	}
}
