---
name: resolve-dependabot-alerts
description: Use when resolving, triaging, or fixing GitHub Dependabot security/vulnerability alerts (GHSA/CVE, "security alert", "dependabot") in a repository, across ecosystems (npm/pnpm/yarn and cargo in depth, others via the alert's ecosystem field). Fetches open alerts with `gh api`, classifies each as fix/dismiss/defer, bumps vulnerable dependencies (including transitive overrides), verifies the lockfile resolves to a patched version plus build/test, then works on a branch with one commit per group, pushes, and opens a PR. Do NOT use for routine non-security dependency bumps or for merging Dependabot version-update PRs.
---

# Resolve Dependabot alerts

Triage and fix GitHub Dependabot **security** alerts end to end:
fetch -> classify -> fix on a branch (one commit per group) -> verify -> push -> PR.
Dismissals are always proposed for explicit approval, never automatic.

## When to use / not use
- Use: "resolve/triage/fix Dependabot alerts", "security alert", "vulnerability", a GHSA/CVE in dependencies, the repo Security tab.
- Don't use: routine dependency upgrades unrelated to security, or just merging Dependabot's own version-update PRs.

## Preconditions
- `gh auth status` shows a token that can read Dependabot alerts: classic `security_events` (or `repo`) scope, or a fine-grained PAT with **Dependabot alerts: read** (read to list; **write** only if dismissing). Opening a PR also needs contents + pull-requests write.
- Resolve the repo once and reuse it as `OWNER/REPO`:
  `gh repo view --json nameWithOwner -q .nameWithOwner` (or parse `git remote get-url origin`).
- Confirm a clean working tree (`git status`) before branching.

## Workflow

### 1. Triage (read-only — change nothing yet)
List open alerts and normalize them:

```bash
gh api --paginate "/repos/OWNER/REPO/dependabot/alerts?state=open&per_page=100" \
  --jq '.[] | {n:.number, sev:.security_advisory.severity, eco:.dependency.package.ecosystem, pkg:.dependency.package.name, manifest:.dependency.manifest_path, range:.security_vulnerability.vulnerable_version_range, fixed:.security_vulnerability.first_patched_version.identifier, ghsa:.security_advisory.ghsa_id, cve:.security_advisory.cve_id, url:.html_url}'
```

Render a table and classify every alert:
- **Fix** — `fixed` (first patched version) exists.
- **Dismiss** — no fix available / false positive / not exploitable / unused. Needs explicit user approval (step 5).
- **Defer** — requires a major upgrade or refactor; record it and skip for now.

Group fixes by **(ecosystem, package)** — or by manifest for monorepos. Also check whether Dependabot already opened security-update PRs:
`gh pr list --author "app/dependabot" --state open`. If a sound one exists, prefer reviewing/merging it over hand-fixing.

Present the plan (fix / dismiss / defer per alert, grouped) and get approval before making any change.

### 2. Branch
```bash
git switch -c fix/dependabot-alerts
```

### 3. Fix loop — one group at a time, one commit per group
For each approved group:
1. Determine direct vs transitive (see Decision rules).
2. Apply the bump (see Per-ecosystem commands).
3. Regenerate the lockfile.
4. **Verify** (see Verification): resolved version >= patched on every path, then build + test.
5. Commit just this group's manifest + lockfile:
   ```bash
   git add <manifest> <lockfile>
   git commit -m "fix(deps): bump <pkg> to <ver> (GHSA-xxxx / CVE-xxxx, alert #N)"
   ```
Repeat until all approved groups are done. Keep groups in separate commits so review and revert stay clean; never bundle unrelated bumps.

### 4. Push
```bash
git push -u origin fix/dependabot-alerts
```

### 5. PR (and dismissals)
```bash
gh pr create --fill --title "Fix Dependabot alerts"
```
PR body should list each fixed alert (pkg old -> new, severity, GHSA/CVE), and anything deferred with a reason.

Dismissals are **never automatic**. Only after explicit per-alert user approval:
```bash
gh api -X PATCH "/repos/OWNER/REPO/dependabot/alerts/N" \
  -f state=dismissed -f dismissed_reason=REASON -f dismissed_comment="..."
# REASON in: tolerable_risk | inaccurate | no_bandwidth | not_used | fix_started
```

## Decision rules
- **Minimal bump**: pick the lowest version >= `first_patched_version` that clears the advisory range; avoid unrelated major upgrades unless required.
- **Direct vs transitive**: a package is direct if it appears in the manifest. Otherwise it is transitive — inspect the graph (`npm ls <pkg>` / `cargo tree -i <pkg>`).
  - Direct -> bump it in the manifest.
  - Transitive -> prefer bumping the parent that pulls it in; if that is not possible, use the ecosystem's override mechanism.
- **`fixed` is not manual**: GitHub marks an alert `fixed` only after it re-scans the pushed change. Do not wait on it — gate on local Verification; the API state catches up after push.

## Verification (no extra installs required)
After regenerating the lockfile, confirm the vulnerable package now resolves to a patched version on **every** path, then build + test:
- npm: `npm ls <pkg>` (no vulnerable versions remain)
- pnpm: `pnpm why <pkg>` / `pnpm ls <pkg> -r`
- yarn: `yarn why <pkg>`
- cargo: `cargo tree -i <pkg>`

Then run the project's build and test. Optionally run `npm audit` / `cargo audit` if present — as a bonus signal, not a gate. Never commit a lockfile that still resolves the vulnerable version.

## Per-ecosystem commands
Dispatch on the alert's `ecosystem` field.

### npm
- Detect: `package.json` + `package-lock.json`
- Direct bump: `npm install <pkg>@<ver>`
- Transitive: add `"overrides": { "<pkg>": "<ver>" }` to package.json, then `npm install`
- Regenerate + check: `npm install` -> `npm ls <pkg>`

### pnpm
- Detect: `pnpm-lock.yaml`
- Direct bump: `pnpm add <pkg>@<ver>`
- Transitive: add `"pnpm": { "overrides": { "<pkg>": "<ver>" } }` to package.json, then `pnpm install`
- Regenerate + check: `pnpm install` -> `pnpm why <pkg>`

### yarn
- Detect: `yarn.lock`
- Direct bump: `yarn up <pkg>@<ver>` (Berry) or `yarn add <pkg>@<ver>` (classic)
- Transitive: add `"resolutions": { "<pkg>": "<ver>" }` to package.json, then `yarn install`
- Regenerate + check: `yarn install` -> `yarn why <pkg>`

### cargo
- Detect: `Cargo.toml` + `Cargo.lock`
- Bump (direct or transitive): `cargo update -p <pkg> --precise <ver>` (works when a dependent's semver requirement allows it)
- If the patched version is outside the dependent's range: bump the dependent crate, or add a `[patch.crates-io]` entry
- Regenerate + check: `cargo update` (scoped) -> `cargo tree -i <pkg>`

### Other ecosystems (template — confirm exact commands before running)
The alert's `ecosystem` tells you which: `pip`, `go`, `maven`, `gradle`, `nuget`, `composer`, `rubygems`, `actions`, `docker`, `pub`. Same general pattern:
1. Direct: bump in the manifest to >= patched.
2. Transitive: use the override/replace mechanism (e.g. Go `replace`, pip constraints) or bump the parent.
3. Regenerate the lockfile.
4. Verify resolved >= patched via that ecosystem's graph command (e.g. `go mod graph`, `mvn dependency:tree`).
5. Build + test.
Verify the precise commands for the ecosystem before applying.

## Safety notes
- npm/pnpm/yarn/cargo execute real code on install (and inherit injected secrets via the local shims). Prefer minimal bumps and review what changed.
- Use `--paginate` for large alert lists and respect API rate limits.
- `gh pr create` requires the branch to be pushed first.
