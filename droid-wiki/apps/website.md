# Website

Active contributors: Nik Anand

## What it does

`website/` is a Next.js 16 marketing site that mirrors the README pitch as a single, scrollable landing page. It's auxiliary — every authoritative doc lives in this wiki or in `docs/registry.md`. The site exists so a casual visitor browsing from a search engine sees the same elevator pitch the README opens with, styled and laid out for a browser instead of GitHub's markdown renderer.

Live deployment lives on Firebase Hosting under two site IDs (`skills-mcp-2026` and `skills-registry` — both point at the same `out/` directory).

## Stack

| Layer | Choice |
| --- | --- |
| Framework | Next.js 16.2.6 |
| Runtime | React 19.2.4 |
| Styling | Tailwind CSS 4 (via `@tailwindcss/postcss`) |
| Language | TypeScript 5 |
| Package manager | Bun (`bun.lock` checked in) |
| Lint | ESLint 9 with `eslint-config-next` |
| Hosting | Firebase Hosting (`firebase.json`, `.firebaserc`) |

The `website/package.json` declares only three runtime dependencies (`next`, `react`, `react-dom`); everything else is dev-only.

## Source layout

| File | Role |
| --- | --- |
| `website/app/layout.tsx` | Root layout — `<html lang="en">`, metadata title + description for SEO/social previews. |
| `website/app/page.tsx` | The whole landing page. One file, ~613 LOC, all sections inlined. |
| `website/app/globals.css` | Tailwind 4 entry point + global CSS variables. |
| `website/app/favicon.ico` | Static favicon. |
| `website/firebase.json` | Hosting config; two sites both pointing at `out/`. |
| `website/.firebaserc` | Firebase project alias (`default: skills-mcp-2026`). |
| `website/next.config.ts` | Next.js config — minimal. |
| `website/postcss.config.mjs` | Tailwind 4 PostCSS plugin wiring. |
| `website/tsconfig.json` | TypeScript config. |
| `website/eslint.config.mjs` | ESLint flat config. |

The site is a single page. There is no routing beyond `/`. Sections inside `page.tsx` are plain components rendered in order: hero, problem, solution, install snippet, feature grid, and footer.

## Build and deploy

```bash
cd website
bun install
bun run dev          # local dev on http://localhost:3000
bun run build        # produces out/ for Firebase Hosting
bun run lint         # eslint flat config
```

`bun run build` runs `next build`, which exports a static site into `out/`. `firebase deploy --only hosting` then uploads it to both `skills-mcp-2026.web.app` and `skills-registry.web.app`. The deploy is manual — there's no CI workflow for the site today.

## "This is NOT the Next.js you know"

`website/AGENTS.md` carries a deliberate warning for any agent touching the site:

> This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.

Next.js 16 changes routing semantics, `app/` directory conventions, and several Server Component defaults from earlier majors. Any edit to the site should consult `node_modules/next/dist/docs/` first rather than relying on training-data recall of older Next.js APIs.

## Scope

The website's job is one page that mirrors the README. It does not host docs (this wiki does), it does not host the installer (`install.sh` is served from `raw.githubusercontent.com`), and it does not host the GitHub Releases tarballs (GitHub does). Treat new requests for site features with skepticism — the canonical surface for everything except the elevator pitch is the README, the wiki, and `docs/registry.md`.

## Key source files

| File | Role |
| --- | --- |
| `website/app/page.tsx` | Single-page landing — every section inlined. |
| `website/app/layout.tsx` | Root layout + metadata. |
| `website/app/globals.css` | Tailwind 4 entry + global vars. |
| `website/firebase.json` | Two-site hosting config. |
| `website/AGENTS.md` | Breaking-changes warning for Next.js 16. |
| `website/package.json` | Dependencies (3 runtime, several dev). |

## Cross-references

- [overview/getting-started](../overview/getting-started.md) — the install command the site embeds.
- [overview/architecture](../overview/architecture.md) — what the site links readers back to.
- [apps/index](index.md) — overview of the three primary deliverables that the site exists to advertise.
