---
name: resolve-dependabot-alerts
description: Use when resolving, triaging, or fixing GitHub Dependabot security/vulnerability alerts (GHSA/CVE, "security alert", "dependabot") in a repository, across ecosystems (npm/pnpm/yarn and cargo in depth, others via the alert's ecosystem field). Fetches open alerts with `gh api`, classifies each as fix/dismiss/defer, bumps vulnerable dependencies (including transitive overrides), verifies the lockfile resolves to a patched version plus build/test, then works on a branch with one commit per group, pushes, and opens a PR. Do NOT use for routine non-security dependency bumps or for merging Dependabot version-update PRs.
author: CraftSamo
license: MIT
---

<Goal>

Triage and fix GitHub Dependabot security alerts end to end: fetch, classify,
fix on a branch, verify, push, and open a PR. Keep one commit per fix group.
Dismissals are proposed for explicit approval only, never automatic.

</Goal>

<Scope>
<UseWhen>

- The user asks to resolve, triage, or fix Dependabot alerts.
- The user mentions "security alert", "vulnerability", GHSA/CVE dependency
  alerts, or the repository Security tab.

</UseWhen>

<DoNotUseWhen>

- Routine dependency upgrades unrelated to security.
- Merely merging Dependabot's own version-update PRs.

</DoNotUseWhen>
</Scope>

<Preconditions>

- `gh auth status` shows a token that can read Dependabot alerts: classic
  `security_events` or `repo` scope, or a fine-grained PAT with Dependabot
  alerts read. Dismissing needs Dependabot alerts write. Opening a PR needs
  contents + pull-requests write.
- Resolve the repo once and reuse it as `OWNER/REPO`:
  `gh repo view --json nameWithOwner -q .nameWithOwner`, or parse
  `git remote get-url origin`.
- Confirm a clean working tree with `git status` before branching.

</Preconditions>

<Steps>

### 1. Triage read-only

List open alerts and normalize them. Change nothing yet.

```bash
gh api --paginate "/repos/OWNER/REPO/dependabot/alerts?state=open&per_page=100" \
  --jq '.[] | {n:.number, sev:.security_advisory.severity, eco:.dependency.package.ecosystem, pkg:.dependency.package.name, manifest:.dependency.manifest_path, range:.security_vulnerability.vulnerable_version_range, fixed:.security_vulnerability.first_patched_version.identifier, ghsa:.security_advisory.ghsa_id, cve:.security_advisory.cve_id, url:.html_url}'
```

Render a table and classify every alert:

- Fix: `fixed` / first patched version exists.
- Dismiss: no fix available, false positive, not exploitable, or unused. Needs
  explicit user approval.
- Defer: requires a major upgrade or refactor. Record it and skip for now.

Group fixes by `(ecosystem, package)`, or by manifest for monorepos. Also check
whether Dependabot already opened security-update PRs:
`gh pr list --author "app/dependabot" --state open`. If a sound PR exists,
prefer reviewing/merging it over hand-fixing.

Present the plan, grouped by fix / dismiss / defer, and get approval before any
change.

### 2. Branch

```bash
git switch -c fix/dependabot-alerts
```

### 3. Fix loop, one group at a time

For each approved group:

1. Determine direct vs transitive. See the DecisionRules section.
2. Apply the bump. See the EcosystemCommands section.
3. Regenerate the lockfile.
4. Verify that every resolved path is patched, then run build + test. See the
   Verify section.
5. Commit only this group's manifest + lockfile:

   ```bash
   git add <manifest> <lockfile>
   git commit -m "fix(deps): bump <pkg> to <ver> (GHSA-xxxx / CVE-xxxx, alert #N)"
   ```

Repeat until all approved groups are done. Keep groups in separate commits so
review and revert stay clean. Never bundle unrelated bumps.

### 4. Push

```bash
git push -u origin fix/dependabot-alerts
```

### 5. PR and dismissals

```bash
gh pr create --fill --title "Fix Dependabot alerts"
```

The PR body should list each fixed alert with package old -> new, severity,
GHSA/CVE, and anything deferred with a reason.

Dismissals are never automatic. Only after explicit per-alert user approval:

```bash
gh api -X PATCH "/repos/OWNER/REPO/dependabot/alerts/N" \
  -f state=dismissed -f dismissed_reason=REASON -f dismissed_comment="..."
# REASON in: tolerable_risk | inaccurate | no_bandwidth | not_used | fix_started
```

</Steps>

<DecisionRules>

- Minimal bump: pick the lowest version greater than or equal to
  `first_patched_version` that clears the advisory range. Avoid unrelated major
  upgrades unless required.
- Direct vs transitive: a package is direct if it appears in the manifest.
  Otherwise it is transitive; inspect the graph with commands such as
  `npm ls <pkg>` or `cargo tree -i <pkg>`.
- Direct dependency: bump it in the manifest.
- Transitive dependency: prefer bumping the parent that pulls it in. If that is
  not possible, use the ecosystem's override mechanism.
- `fixed` is not manual: GitHub marks an alert fixed only after it re-scans the
  pushed change. Do not wait on it. Gate on local verification; the API state
  catches up after push.

</DecisionRules>

<Verify>

After regenerating the lockfile, confirm the vulnerable package now resolves to
a patched version on every path, then build + test.

- npm: `npm ls <pkg>`; no vulnerable versions remain.
- pnpm: `pnpm why <pkg>` or `pnpm ls <pkg> -r`.
- yarn: `yarn why <pkg>`.
- cargo: `cargo tree -i <pkg>`.

Then run the project's build and test. Optionally run `npm audit` or
`cargo audit` if present as a bonus signal, not a gate. Never commit a lockfile
that still resolves the vulnerable version.

</Verify>

<EcosystemCommands>

Dispatch on the alert's `ecosystem` field.

<Npm>

- Detect: `package.json` + `package-lock.json`
- Direct bump: `npm install <pkg>@<ver>`
- Transitive: add `"overrides": { "<pkg>": "<ver>" }` to `package.json`, then
  `npm install`
- Regenerate + check: `npm install` -> `npm ls <pkg>`

</Npm>

<Pnpm>

- Detect: `pnpm-lock.yaml`
- Direct bump: `pnpm add <pkg>@<ver>`
- Transitive: add `"pnpm": { "overrides": { "<pkg>": "<ver>" } }` to
  `package.json`, then `pnpm install`
- Regenerate + check: `pnpm install` -> `pnpm why <pkg>`

</Pnpm>

<Yarn>

- Detect: `yarn.lock`
- Direct bump: `yarn up <pkg>@<ver>` for Berry, or `yarn add <pkg>@<ver>` for
  classic
- Transitive: add `"resolutions": { "<pkg>": "<ver>" }` to `package.json`, then
  `yarn install`
- Regenerate + check: `yarn install` -> `yarn why <pkg>`

</Yarn>

<Cargo>

- Detect: `Cargo.toml` + `Cargo.lock`
- Direct or transitive bump: `cargo update -p <pkg> --precise <ver>` when a
  dependent's semver requirement allows it
- If the patched version is outside the dependent's range, bump the dependent
  crate or add a `[patch.crates-io]` entry
- Regenerate + check: scoped `cargo update` -> `cargo tree -i <pkg>`

</Cargo>

<OtherEcosystems>

For `pip`, `go`, `maven`, `gradle`, `nuget`, `composer`, `rubygems`, `actions`,
`docker`, `pub`, and other ecosystems, confirm exact commands before running.
Use the same pattern:

1. Direct: bump in the manifest to a patched version.
2. Transitive: use the override/replace mechanism, such as Go `replace` or pip
   constraints, or bump the parent.
3. Regenerate the lockfile.
4. Verify resolved version is patched via that ecosystem's graph command, such
   as `go mod graph` or `mvn dependency:tree`.
5. Build + test.

</OtherEcosystems>
</EcosystemCommands>

<AntiPatterns>

- Do not dismiss alerts without explicit per-alert user approval.
- Do not commit a lockfile that still resolves the vulnerable version.
- Do not bundle unrelated dependency bumps into a security fix group.
- Do not use routine dependency-upgrade behavior for a security alert workflow.
- Do not forget `--paginate` for large alert lists.
- Do not run `gh pr create` before the branch has been pushed.
- npm, pnpm, yarn, and cargo execute real code on install and inherit injected
  secrets via local shims; prefer minimal bumps and review what changed.

</AntiPatterns>
