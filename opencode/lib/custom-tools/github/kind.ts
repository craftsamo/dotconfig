import { runGh, runGhJson } from "../exec"
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

export type KindResult = { kind: string; via: "type" | "label"; name: string } | { kind: string; via: "none"; reason: string }

export async function ensureLabel(repo: string, name: string, color: string, description: string, cwd?: string): Promise<boolean> {
  const list = (await runGhJson(withRepo(["label", "list", "--json", "name", "--limit", "200", "--search", name], repo), cwd)) ?? []
  if (list.some((l: any) => sameName(l.name, name))) return false
  await runGh(withRepo(["label", "create", name, "--color", color, "--description", description], repo), cwd)
  return true
}

/** Sets the issue's kind; returns how it landed. `kind` is case-insensitive. */
export async function applyKind(ctx: RepoContext, issue: number, kind: string, cwd?: string): Promise<KindResult> {
  const wanted = kind.trim()
  if (!wanted) return { kind, via: "none", reason: "empty kind" }
  const types = await issueTypes(ctx, cwd)
  const type = types?.find((t) => t.isEnabled && sameName(t.name, wanted))
  if (type) {
    await runGh(withRepo(["issue", "edit", String(issue), "--type", type.name], ctx.nameWithOwner), cwd)
    return { kind: wanted, via: "type", name: type.name }
  }
  const label = `${LABEL_PREFIX}${wanted.toLowerCase()}`
  await ensureLabel(ctx.nameWithOwner, label, KIND_COLORS[wanted.toLowerCase()] ?? "EDEDED", `Kind: ${wanted}`, cwd)
  await runGh(withRepo(["issue", "edit", String(issue), "--add-label", label], ctx.nameWithOwner), cwd)
  return { kind: wanted, via: "label", name: label }
}

/** Reads the kind back from an issue's type or its `type:*` label. */
export function readKind(issueType: string | null | undefined, labels: string[]): string | null {
  if (issueType) return issueType
  const label = labels.find((l) => l.toLowerCase().startsWith(LABEL_PREFIX))
  return label ? label.slice(LABEL_PREFIX.length) : null
}
