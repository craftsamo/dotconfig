import { existsSync, statSync } from "fs"
import { tool } from "../define"
import { runGhJson, runGit, tryGit } from "../exec"

const LIST_MAX = 50

type Entry = { path: string; status: string }

/** Parses `git status --porcelain=v2 --branch -z`. */
function parseStatus(out: string) {
  const branch: { head?: string; oid?: string; upstream?: string; ahead?: number; behind?: number } = {}
  const staged: Entry[] = []
  const unstaged: Entry[] = []
  const untracked: string[] = []
  const conflicted: string[] = []
  const fields = out.split("\0")
  for (let i = 0; i < fields.length; i++) {
    const rec = fields[i]
    if (!rec) continue
    if (rec.startsWith("# branch.oid ")) branch.oid = rec.slice(13)
    else if (rec.startsWith("# branch.head ")) branch.head = rec.slice(14)
    else if (rec.startsWith("# branch.upstream ")) branch.upstream = rec.slice(18)
    else if (rec.startsWith("# branch.ab ")) {
      const m = rec.match(/\+(\d+) -(\d+)/)
      if (m) [branch.ahead, branch.behind] = [Number(m[1]), Number(m[2])]
    } else if (rec.startsWith("? ")) untracked.push(rec.slice(2))
    else if (rec.startsWith("u ")) conflicted.push(rec.split(" ").slice(10).join(" "))
    else if (rec.startsWith("1 ") || rec.startsWith("2 ")) {
      const parts = rec.split(" ")
      const xy = parts[1]
      const path = parts.slice(rec.startsWith("1 ") ? 8 : 9).join(" ")
      // A rename/copy record is followed by its original path.
      const from = rec.startsWith("2 ") ? fields[++i] : undefined
      const shown = from ? `${from} -> ${path}` : path
      if (xy[0] !== ".") staged.push({ path: shown, status: xy[0] })
      if (xy[1] !== ".") unstaged.push({ path, status: xy[1] })
    }
  }
  return { branch, staged, unstaged, untracked, conflicted }
}

const capped = <T>(list: T[]) => ({ count: list.length, items: list.slice(0, LIST_MAX), truncated: list.length > LIST_MAX })

export async function gitPath(cwd: string, name: string): Promise<string> {
  return (await runGit(["rev-parse", "--path-format=absolute", "--git-path", name], cwd)).trim()
}

export async function operation(cwd: string): Promise<string | null> {
  const markers: [string, string][] = [
    ["rebase-merge", "rebase"],
    ["rebase-apply", "rebase"],
    ["MERGE_HEAD", "merge"],
    ["CHERRY_PICK_HEAD", "cherry-pick"],
    ["REVERT_HEAD", "revert"],
    ["BISECT_LOG", "bisect"],
  ]
  for (const [name, op] of markers) if (existsSync(await gitPath(cwd, name))) return op
  return null
}

/** The remote default branch as recorded locally (origin/HEAD), else origin/main or origin/master. */
export async function defaultRef(cwd: string): Promise<string | null> {
  const head = await tryGit(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], cwd)
  if (head.ok && head.stdout.trim()) return head.stdout.trim()
  for (const ref of ["origin/main", "origin/master"])
    if ((await tryGit(["rev-parse", "--verify", "--quiet", `${ref}^{commit}`], cwd)).ok) return ref
  return null
}

async function counts(cwd: string, range: string): Promise<{ ahead: number; behind: number } | null> {
  const res = await tryGit(["rev-list", "--left-right", "--count", range], cwd)
  if (!res.ok) return null
  const [behind, ahead] = res.stdout.trim().split(/\s+/).map(Number)
  return { ahead, behind }
}

export const state = tool({
  description:
    "One read-only snapshot of where the repository stands, instead of chaining git status / log / diff / branch: the branch, its upstream and ahead/behind, the remote default branch with the merge-base and the branch's own commits since it, staged / unstaged / untracked / conflicted files, a rebase, merge, cherry-pick, revert or bisect in progress, stashes, worktrees, when origin was last fetched, and the branch's pull request. Reads only local refs (run `git fetch` first for fresh remote state); the PR lookup uses gh and is skipped with pr:false.",
  args: {
    pr: tool.schema.boolean().optional().describe("Look up the branch's pull request with gh (default true)."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const root = (await runGit(["rev-parse", "--show-toplevel"], cwd)).trim()
    const st = parseStatus(await runGit(["status", "--porcelain=v2", "--branch", "-z"], cwd))
    const detached = st.branch.head === "(detached)"
    const unborn = st.branch.oid === "(initial)"

    const def = await defaultRef(cwd)
    let base: any = null
    if (def && !unborn) {
      const mergeBase = await tryGit(["merge-base", "HEAD", def], cwd)
      const own = mergeBase.ok
        ? (await runGit(["log", "--format=%h %s", `-${LIST_MAX + 1}`, `${def}..HEAD`], cwd)).split("\n").filter(Boolean)
        : []
      base = {
        ref: def,
        mergeBase: mergeBase.ok ? mergeBase.stdout.trim() : null,
        ...(await counts(cwd, `${def}...HEAD`)),
        commits: own.slice(0, LIST_MAX),
        commitsTruncated: own.length > LIST_MAX,
      }
    }

    const stashes = (await tryGit(["stash", "list", "--format=%gd %s"], cwd)).stdout.split("\n").filter(Boolean)
    const worktrees: { path: string; branch: string | null; current: boolean }[] = []
    let cur: { path: string; branch: string | null } | null = null
    for (const line of (await runGit(["worktree", "list", "--porcelain"], cwd)).split("\n")) {
      if (line.startsWith("worktree ")) {
        cur = { path: line.slice(9), branch: null }
        worktrees.push({ ...cur, current: false })
      } else if (line.startsWith("branch ") && cur) worktrees[worktrees.length - 1].branch = line.slice(7).replace(/^refs\/heads\//, "")
    }
    for (const w of worktrees) w.current = w.path === root

    const fetchHead = await gitPath(cwd, "FETCH_HEAD")
    const lastFetch = existsSync(fetchHead) ? statSync(fetchHead).mtime.toISOString() : null

    let pr: any = null
    if ((args.pr ?? true) && !detached && !unborn) {
      try {
        pr = await runGhJson(["pr", "view", "--json", "number,title,state,isDraft,url,baseRefName,headRefName"], cwd)
      } catch {
        pr = null
      }
    }

    return JSON.stringify(
      {
        root,
        branch: detached ? null : (st.branch.head ?? null),
        head: unborn ? null : (st.branch.oid ?? null),
        detached,
        unborn,
        upstream: st.branch.upstream ? { ref: st.branch.upstream, ahead: st.branch.ahead ?? 0, behind: st.branch.behind ?? 0 } : null,
        base,
        operation: await operation(cwd),
        conflicted: st.conflicted,
        staged: capped(st.staged),
        unstaged: capped(st.unstaged),
        untracked: capped(st.untracked),
        clean: !st.staged.length && !st.unstaged.length && !st.untracked.length && !st.conflicted.length,
        stashes,
        worktrees,
        lastFetch,
        pr,
      },
      null,
      2,
    )
  },
})
