import { exec, runGhJson, runGit, tryGit } from "../exec"
import { localStack } from "./related"
import { defaultRef } from "./state"

/**
 * The one rule for rewriting commits (amend, fixup, rebase): a task branch's
 * own commits may be rewritten even once pushed — the push then needs
 * `--force-with-lease` — but never the default branch, a branch GitHub
 * protects against force pushes, commits already on the default branch, or
 * commits another remote branch holds too (except the layers above this one
 * in the same native stack, which `gh stack rebase` moves along).
 */

export type Refusal = { rule: "detached" | "default-branch" | "merged" | "shared" | "protected"; message: string }

export type RewriteCheck = {
  allowed: boolean
  branch: string | null
  /** The branch's own remote refs that already hold the commits being rewritten. */
  published: string[]
  needsForcePush: boolean
  refusals: Refusal[]
  warnings: string[]
}

export async function currentBranch(cwd: string): Promise<string | null> {
  const res = await tryGit(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd)
  return res.ok ? res.stdout.trim() || null : null
}

const isAncestor = async (cwd: string, a: string, b: string) => (await tryGit(["merge-base", "--is-ancestor", a, b], cwd)).ok

type RemoteRef = { remote: string; name: string; ref: string }

const remotesOf = async (cwd: string) => (await tryGit(["remote"], cwd)).stdout.split("\n").map((r) => r.trim()).filter(Boolean)

/** Splits `<remote>/<name>` against the known remotes (a remote name may hold no slash, a branch may). */
function splitRef(ref: string, remotes: string[]): RemoteRef | null {
  const remote = remotes.filter((r) => ref.startsWith(`${r}/`)).sort((a, b) => b.length - a.length)[0]
  return remote ? { remote, name: ref.slice(remote.length + 1), ref } : null
}

/**
 * Remote refs that count as this branch's own: `<remote>/<branch>` on every
 * remote, and where it pushes. An upstream counts only under the branch's own
 * name: a branch cut from `origin/feat-a` tracks it, but feat-a is someone
 * else's work.
 */
export async function ownRemoteRefs(cwd: string, branch: string): Promise<RemoteRef[]> {
  const remotes = await remotesOf(cwd)
  const refs = new Map<string, RemoteRef>()
  for (const remote of remotes) refs.set(`${remote}/${branch}`, { remote, name: branch, ref: `${remote}/${branch}` })
  const push = await tryGit(["rev-parse", "--abbrev-ref", "--symbolic-full-name", `${branch}@{push}`], cwd)
  const pushRef = push.ok ? splitRef(push.stdout.trim(), remotes) : null
  if (pushRef && pushRef.name === branch) refs.set(pushRef.ref, pushRef)
  const existing = []
  for (const r of refs.values())
    if ((await tryGit(["rev-parse", "--verify", "--quiet", `refs/remotes/${r.ref}^{commit}`], cwd)).ok) existing.push(r)
  return existing
}

/** Whether pushing HEAD to the branch's own remote refs now needs a force push. */
export async function needsForcePush(cwd: string, branch: string): Promise<boolean> {
  for (const r of await ownRemoteRefs(cwd, branch)) if (!(await isAncestor(cwd, `refs/remotes/${r.ref}`, "HEAD"))) return true
  return false
}

function githubRepo(url: string): string | null {
  const m = url.trim().match(/github\.com[:/]([^/]+\/[^/]+?)(?:\.git)?\/?$/)
  return m ? m[1] : null
}

const branchPath = (name: string) => name.split("/").map(encodeURIComponent).join("/")

/** Why GitHub refuses a force push to `name`, null when it allows one, undefined when it could not be read. */
async function forcePushBlock(repo: string, name: string, cwd: string): Promise<string | null | undefined> {
  let rules: any
  try {
    rules = await runGhJson(["api", `repos/${repo}/rules/branches/${branchPath(name)}`], cwd)
  } catch {
    return undefined
  }
  if (Array.isArray(rules) && rules.some((r: any) => r?.type === "non_fast_forward")) return "a ruleset blocks force pushes"
  let protectedFlag: unknown
  try {
    protectedFlag = await runGhJson(["api", `repos/${repo}/branches/${branchPath(name)}`, "--jq", ".protected"], cwd)
  } catch {
    return undefined
  }
  if (protectedFlag !== true) return null
  // `protected` is also true for a branch only rulesets cover (read above): 404
  // here means no classic protection. Its settings need admin access, so any
  // other unreadable answer counts as blocked.
  const res = await exec(["gh", "api", `repos/${repo}/branches/${branchPath(name)}/protection`, "--jq", ".allow_force_pushes.enabled"], { cwd })
  if (res.ok) return res.stdout.trim() === "true" ? null : "branch protection blocks force pushes"
  const error = `${res.stdout}\n${res.stderr}`
  if (/Branch not protected/i.test(error)) return null
  // A bare 404 can also hide the endpoint from a caller without access.
  if (/HTTP 404/.test(error)) return undefined
  return "branch protection blocks force pushes"
}

/**
 * The commits a rewrite replaces — reachable from HEAD but not from `exclude`
 * — and their roots: the ones whose parents all lie outside. A ref holds a
 * commit of the range exactly when it holds one of the roots, merged-in side
 * branches included.
 */
async function rangeRoots(cwd: string, exclude: string[]): Promise<string[]> {
  const rows = (await runGit(["rev-list", "--parents", "HEAD", "--not", ...exclude], cwd))
    .split("\n")
    .filter(Boolean)
    .map((l) => l.split(" "))
  const inRange = new Set(rows.map((r) => r[0]))
  return rows.filter((r) => r.slice(1).every((p) => !inRange.has(p))).map((r) => r[0])
}

/**
 * Checks a rewrite of every commit after `base` up to HEAD — by default after
 * the parents of `oldest`, i.e. `oldest` and everything since.
 */
export async function checkRewrite(cwd: string, oldest: string, base?: string): Promise<RewriteCheck> {
  const refusals: Refusal[] = []
  const warnings: string[] = []
  const branch = await currentBranch(cwd)
  if (!branch)
    return {
      allowed: false,
      branch: null,
      published: [],
      needsForcePush: false,
      refusals: [{ rule: "detached", message: "HEAD is detached; check out the task branch first." }],
      warnings,
    }

  const def = await defaultRef(cwd)
  const defName = def ? def.slice(def.indexOf("/") + 1) : null
  const remotes = await remotesOf(cwd)
  // Without a base the rewrite starts at `oldest`; the default branch is left
  // out too, since a fold keeps the base and never replays what was merged in from it.
  const exclude = base
    ? [base]
    : [...(await runGit(["rev-parse", `${oldest}^@`], cwd)).split("\n").filter(Boolean), ...(def ? [def] : [])]
  const roots = await rangeRoots(cwd, exclude)

  if (!def && remotes.length)
    refusals.push({
      rule: "default-branch",
      message: "The remote default branch is unknown here (no origin/HEAD, origin/main or origin/master); run `git remote set-head origin --auto` first.",
    })
  else if (defName ? branch === defName : ["main", "master"].includes(branch))
    refusals.push({ rule: "default-branch", message: `${branch} is the default branch; its history is never rewritten. Make a new commit instead.` })
  else if (def) {
    for (const commit of [oldest, ...roots])
      if (await isAncestor(cwd, commit, def)) {
        refusals.push({
          rule: "merged",
          message: `${commit.slice(0, 12)} is already on ${def}; make a new commit that fixes it and links it (linked-fix).`,
        })
        break
      }
  }

  const own = await ownRemoteRefs(cwd, branch)
  const ownRefs = new Set(own.map((r) => r.ref))
  const containing = roots.length
    ? (await tryGit(["branch", "-r", ...roots.flatMap((r) => ["--contains", r]), "--format=%(refname)"], cwd)).stdout
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => l && !l.endsWith("/HEAD"))
        .map((l) => l.replace(/^refs\/remotes\//, ""))
    : []
  const holding = own.filter((r) => containing.includes(r.ref))
  let others = containing.filter((ref) => !ownRefs.has(ref) && ref !== def)
  if (others.length) {
    const stack = await localStack(branch, cwd)
    if (stack) {
      const above = new Set(stack.layers.filter((l: any) => l.position > stack.position).map((l: any) => l.head))
      others = others.filter((ref) => !above.has(splitRef(ref, remotes)?.name ?? ref))
    }
  }
  if (others.length)
    refusals.push({
      rule: "shared",
      message: `Other branches also hold these commits (${others.slice(0, 5).join(", ")}); rewriting them would break that work. Make a new commit instead.`,
    })

  if (!refusals.length) {
    for (const r of holding) {
      const url = (await tryGit(["remote", "get-url", r.remote], cwd)).stdout
      const repo = githubRepo(url)
      if (!repo) {
        if (/github/i.test(url)) warnings.push(`${r.remote} is not a github.com URL this tool can read; its branch protection was not checked.`)
        continue
      }
      const block = await forcePushBlock(repo, r.name, cwd)
      if (block === undefined) warnings.push(`Could not read GitHub's protection for ${r.ref}; GitHub still refuses the push if it is protected.`)
      else if (block) refusals.push({ rule: "protected", message: `${r.ref} cannot be force-pushed: ${block}. Make a new commit instead.` })
    }
  }

  const published = holding.map((r) => r.ref)
  return { allowed: !refusals.length, branch, published, needsForcePush: published.length > 0, refusals, warnings }
}
