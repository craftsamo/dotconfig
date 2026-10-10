import { readFileSync } from "fs"
import { basename, join } from "path"
import { tool } from "../define"
import { runGit, tryGit } from "../exec"
import { operation } from "./state"

const REGION_MAX = 20
const SIDE_LINES_MAX = 40

/** Lockfiles are regenerated, never merged by hand: resolve the manifest, keep one side, rerun the tool. */
const LOCKFILES: Record<string, string> = {
  "pnpm-lock.yaml": "pnpm install --lockfile-only",
  "package-lock.json": "npm install --package-lock-only",
  "npm-shrinkwrap.json": "npm install --package-lock-only",
  "yarn.lock": "yarn install",
  "bun.lock": "bun install",
  "bun.lockb": "bun install",
  "Cargo.lock": "cargo update --workspace",
  "uv.lock": "uv lock",
  "poetry.lock": "poetry lock --no-update",
  "go.sum": "go mod tidy",
  "Gemfile.lock": "bundle lock",
  "composer.lock": "composer update --lock",
}

// Porcelain v2 `u` records: what each side did to the path.
const KINDS: Record<string, string> = {
  UU: "both modified",
  AA: "both added",
  DD: "both deleted",
  AU: "added by us",
  UA: "added by them",
  DU: "deleted by us",
  UD: "deleted by them",
}

type Region = { line: number; ours: string[]; base?: string[]; theirs: string[]; truncated: boolean }

/** Conflict-marker regions of a file, with each side's lines (diff3 base when present). */
export function parseRegions(text: string): Region[] {
  const regions: Region[] = []
  const lines = text.split("\n")
  let cur: Region | null = null
  let side: "ours" | "base" | "theirs" = "ours"
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i]
    if (l.startsWith("<<<<<<<")) {
      cur = { line: i + 1, ours: [], theirs: [], truncated: false }
      side = "ours"
    } else if (cur && l.startsWith("|||||||")) {
      cur.base = []
      side = "base"
    } else if (cur && l.startsWith("=======")) side = "theirs"
    else if (cur && l.startsWith(">>>>>>>")) {
      regions.push(cur)
      cur = null
    } else if (cur) {
      const list = cur[side]!
      if (list.length < SIDE_LINES_MAX) list.push(l)
      else cur.truncated = true
    }
  }
  return regions
}

async function side(cwd: string, ref: string) {
  const res = await tryGit(["log", "-1", "--format=%H%x00%s", ref], cwd)
  if (!res.ok) return null
  const [sha, subject] = res.stdout.trim().split("\0")
  return { ref, sha, subject }
}

export const conflicts = tool({
  description:
    "Read-only map of the conflicts left by a merge, rebase, cherry-pick or revert: which operation is running, what `ours` and `theirs` are in it (in a rebase `ours` is the branch being rebased onto and `theirs` the commit being replayed), and for each conflicted file how each side changed it plus its conflict-marker regions with both sides' lines. Lockfiles are flagged with the command that regenerates them instead of a hand merge. Resolves nothing; edit the files, then `git add` them and continue the operation.",
  args: {
    paths: tool.schema.array(tool.schema.string()).optional().describe("Only these conflicted files (default: all)."),
  },
  async execute(args, context) {
    return JSON.stringify(await conflictMap(context.worktree, args.paths), null, 2)
  },
})

/** The conflicts the running operation left: its sides and each conflicted file's regions. */
export async function conflictMap(cwd: string, paths?: string[]) {
  const root = (await runGit(["rev-parse", "--show-toplevel"], cwd)).trim()
  const op = await operation(cwd)
  const status = await runGit(["status", "--porcelain=v2", "-z"], cwd)
  let files = status
    .split("\0")
    .filter((r) => r.startsWith("u "))
    .map((r) => {
      const parts = r.split(" ")
      return { path: parts.slice(10).join(" "), xy: parts[1] }
    })
  if (paths?.length) files = files.filter((f) => paths.includes(f.path))

  const theirsRef = { merge: "MERGE_HEAD", rebase: "REBASE_HEAD", "cherry-pick": "CHERRY_PICK_HEAD", revert: "REVERT_HEAD" }[op ?? ""]
  const sides = {
    ours: await side(cwd, "HEAD"),
    theirs: theirsRef ? await side(cwd, theirsRef) : null,
    note:
      op === "rebase"
        ? "In a rebase, ours is the branch being rebased onto and theirs is your commit being replayed."
        : op === "revert"
          ? "In a revert, theirs is the commit being reverted; its inverse is what is being applied."
          : "ours is the current branch (HEAD); theirs is what is being brought in.",
  }

  const out = files.map((f) => {
    const name = basename(f.path)
    const kind = KINDS[f.xy] ?? f.xy
    const lockfile = LOCKFILES[name]
    if (lockfile)
      return {
        path: f.path,
        kind,
        lockfile: true,
        resolve: `Resolve its manifest first, keep one side (\`git checkout --ours -- ${f.path}\` keeps ${op === "rebase" ? "the branch being rebased onto" : "the current branch"}), run \`${lockfile}\` where the lockfile lives, then \`git add ${f.path}\`.`,
      }
    let text: string | null = null
    try {
      text = readFileSync(join(root, f.path), "utf8")
    } catch {
      // deleted on our side, or unreadable
    }
    if (text === null || text.includes("\0")) return { path: f.path, kind, lockfile: false, binary: text !== null, regions: [] }
    const regions = parseRegions(text)
    return {
      path: f.path,
      kind,
      lockfile: false,
      regionCount: regions.length,
      regions: regions.slice(0, REGION_MAX),
      regionsTruncated: regions.length > REGION_MAX,
    }
  })

  return { operation: op, sides, count: out.length, files: out }
}
