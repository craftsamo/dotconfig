import { existsSync, readFileSync } from "fs"
import { join } from "path"
import { tool } from "../define"
import { exec, runGit, tryGit } from "../exec"
import { conflictMap } from "./conflicts"
import { localStack } from "./related"
import { checkRewrite, currentBranch, needsForcePush } from "./rewrite"
import { defaultRef, gitPath, operation } from "./state"

const tail = (text: string, n = 40) => text.trim().split("\n").slice(-n).join("\n")
const FIXUP = /^(fixup|squash|amend)! /

// The todo list is taken as git writes it and a replayed message as it is:
// no editor ever opens, so the call cannot hang on one.
const NO_EDITOR = { GIT_SEQUENCE_EDITOR: "true", GIT_EDITOR: "true" }

const rebaseGit = (argv: string[], cwd: string, signal?: AbortSignal) =>
  exec(["git", ...argv], { cwd, env: { ...process.env, ...NO_EDITOR }, signal })

/** A file of the running rebase's state directory (orig-head, onto), if any. */
async function rebaseState(cwd: string, name: string): Promise<string | null> {
  for (const dir of ["rebase-merge", "rebase-apply"]) {
    const path = join(await gitPath(cwd, dir), name)
    if (existsSync(path)) return readFileSync(path, "utf8").trim() || null
  }
  return null
}

const subjects = async (cwd: string, range: string) =>
  (await runGit(["log", "--reverse", "--format=%h %s", range], cwd)).split("\n").filter(Boolean)

/** What the rebase left: done (with the new history), stopped on conflicts, or failed. */
async function outcome(
  cwd: string,
  res: { ok: boolean; code: number; stdout: string; stderr: string; killed?: string },
  before: string | null,
  onto: { ref: string | null; sha: string },
  fixupsBefore: number | null,
  warnings: string[],
) {
  const output = tail(`${res.stdout}\n${res.stderr}`)
  const inProgress = (await operation(cwd)) === "rebase"
  if (res.killed)
    return {
      rebased: false,
      stoppedAt: "stopped",
      before,
      onto,
      inProgress,
      output,
      ...(inProgress ? { next: "The rebase is still in progress: git_rebase continue, or abort to restore the branch." } : {}),
    }
  if (inProgress) {
    const stoppedOn = (await tryGit(["log", "-1", "--format=%h %s", "REBASE_HEAD"], cwd)).stdout.trim() || null
    const conflicts = await conflictMap(cwd)
    if (!conflicts.count) {
      // Only git's own words prove the commit has nothing left; any other stop
      // (an untracked file in the way, a signing failure) must not be skipped.
      // Hint and todo lines quote commit subjects, which may say anything.
      const gitSays = output
        .split("\n")
        .filter((l) => !/^\s*(hint:|(pick|fixup|squash|reword|edit|drop|exec) )/.test(l))
        .join("\n")
      const empty = /is now empty|nothing to commit|nothing added to commit/i.test(gitSays)
      return {
        rebased: false,
        stoppedAt: empty ? "empty" : "rebase",
        inProgress: true,
        before,
        onto,
        stoppedOn,
        output,
        next: empty
          ? "Nothing is left of this commit (its change is already in the base): git_rebase skip drops it; abort restores the branch."
          : "Fix what the output names, then git_rebase continue; abort restores the branch.",
        ...(warnings.length ? { warnings } : {}),
      }
    }
    return {
      rebased: false,
      stoppedAt: "conflicts",
      before,
      onto,
      stoppedOn,
      conflicts,
      output,
      next: "Resolve each file, `git add` it, then git_rebase continue; skip drops this commit, abort restores the branch.",
      ...(warnings.length ? { warnings } : {}),
    }
  }
  if (!res.ok) return { rebased: false, stoppedAt: "rebase", before, onto, exitCode: res.code, output }
  const branch = await currentBranch(cwd)
  const after = (await runGit(["rev-parse", "HEAD"], cwd)).trim()
  const commits = await subjects(cwd, `${onto.sha}..HEAD`)
  const fixups = (list: string[]) => list.filter((s) => FIXUP.test(s.slice(s.indexOf(" ") + 1))).length
  return {
    rebased: true,
    branch,
    before,
    after,
    onto,
    commits,
    ...(fixupsBefore !== null ? { folded: fixupsBefore - fixups(commits) } : {}),
    needsForcePush: branch ? await needsForcePush(cwd, branch) : false,
    undo: before && before !== after ? `git reset --keep ${before}` : null,
    ...(warnings.length ? { warnings } : {}),
  }
}

export const rebase = tool({
  description:
    "Rebase the current task branch without an editor, folding fixup!/squash! commits in (autosquash). start: fetch `onto` (default: the remote default branch) and replay the branch's own commits on its latest state, dropping any whose change the base already has; keepBase: true keeps the current base and only folds the fixups (also on a native stack layer, then `gh stack rebase` moves the layers above). Refuses with uncommitted changes, an operation in progress, a detached HEAD, a native stack layer without keepBase (use `gh stack rebase`), or a rewrite that git_amend_check's rule forbids (the default branch, commits already on it or held by another remote branch, a branch GitHub protects). On conflicts it stops and returns the conflict map: resolve, `git add`, then continue (or skip / abort). Returns the commit before (to undo), the new commits, how many fixups were folded, and needsForcePush when the pushed branch must now be pushed with --force-with-lease. Never pushes.",
  args: {
    action: tool.schema.enum(["start", "continue", "skip", "abort"]).describe("start a rebase, or continue / skip / abort the one in progress."),
    onto: tool.schema
      .string()
      .optional()
      .describe("start: the branch to rebase onto, as its name on origin (fetched first) or a local ref. Default: the remote default branch."),
    keepBase: tool.schema.boolean().optional().describe("start: keep the current base; only fold fixup!/squash! commits (no fetch)."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const signal = context.signal
    const op = await operation(cwd)

    if (args.action === "abort") {
      if (op !== "rebase") throw new Error("No rebase is in progress.")
      const res = await rebaseGit(["rebase", "--abort"], cwd, signal)
      if (!res.ok) throw new Error(`git rebase --abort failed:\n${tail(`${res.stdout}\n${res.stderr}`)}`)
      return JSON.stringify({ aborted: true, branch: await currentBranch(cwd), head: (await runGit(["rev-parse", "HEAD"], cwd)).trim() }, null, 2)
    }

    if (args.action === "continue" || args.action === "skip") {
      if (op !== "rebase") throw new Error("No rebase is in progress.")
      const before = await rebaseState(cwd, "orig-head")
      const ontoSha = (await rebaseState(cwd, "onto")) ?? before ?? "HEAD"
      const onto = { ref: null, sha: ontoSha }
      if (args.action === "continue") {
        const unmerged = (await runGit(["diff", "--name-only", "--diff-filter=U"], cwd)).split("\n").filter(Boolean)
        if (unmerged.length)
          return JSON.stringify(
            {
              rebased: false,
              stoppedAt: "conflicts",
              before,
              unresolved: unmerged,
              conflicts: await conflictMap(cwd),
              next: "These files are still unmerged: resolve them and `git add` each before continuing.",
            },
            null,
            2,
          )
      }
      const res = await rebaseGit(["rebase", args.action === "continue" ? "--continue" : "--skip"], cwd, signal)
      return JSON.stringify(await outcome(cwd, res, before, onto, null, []), null, 2)
    }

    // start
    if (op) throw new Error(`A ${op} is in progress; finish or abort it first.`)
    const branch = await currentBranch(cwd)
    if (!branch) throw new Error("HEAD is detached; check out the task branch first.")
    if ((await runGit(["status", "--porcelain=v1", "--untracked-files=no"], cwd)).trim())
      throw new Error("There are uncommitted changes; commit them (or stash them) before rebasing.")
    if (args.onto?.trim().startsWith("-")) throw new Error("`onto` must name a branch or ref, not an option.")
    const stack = await localStack(branch, cwd)
    if (stack && !args.keepBase)
      throw new Error(`${branch} is layer ${stack.position} of ${stack.size} of a native stack; rebase it with \`gh stack rebase\` so every layer moves together.`)

    const warnings: string[] = []
    if (stack && stack.position < stack.size)
      warnings.push("Layers above this one still hold the old commits: run `gh stack rebase` to move them onto the folded layer.")
    const def = await defaultRef(cwd)
    let ontoRef: string
    if (args.keepBase) {
      // On an upper stack layer the base is the layer below (its local branch,
      // which gh stack keeps current), not the trunk.
      const below = args.onto?.trim() ? undefined : (stack?.below?.head as string | undefined)
      const name = args.onto?.trim()
      const ref = below
        ? (await tryGit(["rev-parse", "--verify", "--quiet", `refs/heads/${below}`], cwd)).ok
          ? below
          : `origin/${below}`
        : name
          ? (await tryGit(["rev-parse", "--verify", "--quiet", `refs/remotes/origin/${name}`], cwd)).ok
            ? `origin/${name}`
            : name
          : def
      if (!ref) throw new Error("No remote default branch is known here; pass `onto`.")
      ontoRef = ref
    } else {
      const name = args.onto?.trim() || (def ? def.slice(def.indexOf("/") + 1) : "")
      if (!name) throw new Error("No remote default branch is known here; pass `onto`.")
      const hasOrigin = (await tryGit(["remote", "get-url", "origin"], cwd)).ok
      if (hasOrigin) {
        const fetched = await exec(["git", "fetch", "--quiet", "origin", name], { cwd, signal })
        if (!fetched.ok && (await tryGit(["rev-parse", "--verify", "--quiet", `refs/remotes/origin/${name}`], cwd)).ok)
          warnings.push(`fetching origin ${name} failed; rebasing onto origin/${name} as of the last fetch.`)
      }
      ontoRef = (await tryGit(["rev-parse", "--verify", "--quiet", `refs/remotes/origin/${name}^{commit}`], cwd)).ok ? `origin/${name}` : name
    }
    const ontoSha = (await tryGit(["rev-parse", "--verify", "--quiet", `${ontoRef}^{commit}`], cwd)).stdout.trim()
    if (!ontoSha)
      throw new Error(
        stack && !args.onto?.trim()
          ? `The layer below (${ontoRef}) no longer exists; run \`gh stack rebase\` first, or pass \`onto\`.`
          : `Unknown branch or ref: ${ontoRef}.`,
      )
    const mergeBase = (await runGit(["merge-base", "HEAD", ontoSha], cwd)).trim()
    const base = args.keepBase ? mergeBase : ontoSha
    const onto = { ref: ontoRef, sha: base }

    const own = (await runGit(["rev-list", "--reverse", `${mergeBase}..HEAD`], cwd)).split("\n").filter(Boolean)
    const ownSubjects = await subjects(cwd, `${mergeBase}..HEAD`)
    const fixupCount = ownSubjects.filter((s) => FIXUP.test(s.slice(s.indexOf(" ") + 1))).length
    if (base === mergeBase && !fixupCount)
      return JSON.stringify({ rebased: false, upToDate: true, branch, onto, commits: ownSubjects, ...(warnings.length ? { warnings } : {}) }, null, 2)

    if (own.length) {
      const check = await checkRewrite(cwd, own[0], mergeBase)
      if (!check.allowed)
        return JSON.stringify({ rebased: false, stoppedAt: "rewrite", refusals: check.refusals, warnings: [...warnings, ...check.warnings] }, null, 2)
      warnings.push(...check.warnings)
    }

    const before = (await runGit(["rev-parse", "HEAD"], cwd)).trim()
    // A commit whose change the base already has is dropped, not stopped on.
    const res = await rebaseGit(["rebase", "-i", "--autosquash", "--empty=drop", ...(args.keepBase ? [mergeBase] : [ontoSha])], cwd, signal)
    return JSON.stringify(await outcome(cwd, res, before, onto, fixupCount, warnings), null, 2)
  },
})
