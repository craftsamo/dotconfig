import { exec, runGh, runGhJson } from "../exec"
import { sameName } from "./refs"
import { issueTypes, withRepo, type RepoContext } from "./repo"

/**
 * An issue's kind (feature, bug, task, ...) lands where the repository can
 * hold it: as the organization's Issue Type when the owner is an organization
 * that defines a matching type, else as a `type:<kind>` label (Issue Types are
 * organization-only). Labels are created on first use, with one color per
 * well-known kind.
 */

export const LABEL_PREFIX = "type:"

const KIND_COLORS: Record<string, string> = {
  feature: "0E8A16",
  enhancement: "1D76DB",
  bug: "D73A4A",
  task: "6F42C1",
  chore: "BFD4F2",
  docs: "0075CA",
  test: "FBCA04",
  design: "E99695",
}

export type KindResult = { kind: string; via: "type" | "label"; name: string; removedLabels: string[]; note?: string } | { kind: string; via: "none"; reason: string }

export async function ensureLabel(repo: string, name: string, color: string, description: string, cwd?: string): Promise<boolean> {
  const list = (await runGhJson(withRepo(["label", "list", "--json", "name", "--limit", "200", "--search", name], repo), cwd)) ?? []
  if (list.some((l: any) => sameName(l.name, name))) return false
  await runGh(withRepo(["label", "create", name, "--color", color, "--description", description], repo), cwd)
  return true
}

async function currentTypeLabels(repo: string, issue: number, cwd?: string): Promise<string[]> {
  const data = await runGhJson(withRepo(["issue", "view", String(issue), "--json", "labels"], repo), cwd)
  return (data?.labels ?? []).map((l: any) => String(l.name)).filter((n: string) => n.toLowerCase().startsWith(LABEL_PREFIX))
}

/**
 * Sets the issue's kind and returns how it landed. One kind at a time: the
 * other `type:*` labels come off, and so does every one when the kind lands
 * as an Issue Type. `kind` is case-insensitive.
 */
export async function applyKind(ctx: RepoContext, issue: number, kind: string, cwd?: string): Promise<KindResult> {
  const wanted = kind.trim()
  if (!wanted) return { kind, via: "none", reason: "empty kind" }
  const r = ctx.nameWithOwner
  const n = String(issue)
  const types = await issueTypes(ctx, cwd)
  const type = types?.find((t) => t.isEnabled && sameName(t.name, wanted))
  const label = `${LABEL_PREFIX}${wanted.toLowerCase()}`
  const stale = (await currentTypeLabels(r, issue, cwd)).filter((l) => type || !sameName(l, label))
  const removeStale = async () => {
    for (const l of stale) await runGh(withRepo(["issue", "edit", n, "--remove-label", l], r), cwd)
  }
  if (type) {
    const res = await exec(["gh", "issue", "edit", n, "--type", type.name, "--repo", r], { cwd })
    if (res.ok) {
      await removeStale()
      return { kind: wanted, via: "type", name: type.name, removedLabels: stale }
    }
    // An older gh lacks --type; the label carries the kind until it is upgraded.
    const note = `gh issue edit --type failed (${res.stderr.trim().split("\n")[0]}); labelled instead`
    await ensureLabel(r, label, KIND_COLORS[wanted.toLowerCase()] ?? "EDEDED", `Kind: ${wanted}`, cwd)
    await runGh(withRepo(["issue", "edit", n, "--add-label", label], r), cwd)
    const others = stale.filter((l) => !sameName(l, label))
    for (const l of others) await runGh(withRepo(["issue", "edit", n, "--remove-label", l], r), cwd)
    return { kind: wanted, via: "label", name: label, removedLabels: others, note }
  }
  await ensureLabel(r, label, KIND_COLORS[wanted.toLowerCase()] ?? "EDEDED", `Kind: ${wanted}`, cwd)
  await runGh(withRepo(["issue", "edit", n, "--add-label", label], r), cwd)
  await removeStale()
  return { kind: wanted, via: "label", name: label, removedLabels: stale }
}

/** Reads the kind back from an issue's type or its `type:*` label. */
export function readKind(issueType: string | null | undefined, labels: string[]): string | null {
  if (issueType) return issueType
  const label = labels.find((l) => l.toLowerCase().startsWith(LABEL_PREFIX))
  return label ? label.slice(LABEL_PREFIX.length) : null
}
