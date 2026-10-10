import { resolve, sep } from "path"
import { tool } from "../define"
import { runGit, withTempFile } from "../exec"
import { dedupe, scanDiff } from "./secrets"

type Hunk = {
  id: number
  file: string
  header: string
  preamble: string
  body: string
  added: number
  removed: number
  binary: boolean
}

function parseHunks(diff: string): Hunk[] {
  const hunks: Hunk[] = []
  const lines = diff.split("\n")
  let id = 0
  let i = 0
  while (i < lines.length) {
    if (!lines[i].startsWith("diff --git")) {
      i++
      continue
    }
    const fm = lines[i].match(/^diff --git a\/(.*) b\/(.*)$/)
    const file = fm ? fm[2] : ""
    const preambleLines = [lines[i]]
    i++
    let binary = false
    while (i < lines.length && !lines[i].startsWith("@@") && !lines[i].startsWith("diff --git")) {
      if (lines[i].startsWith("Binary files")) binary = true
      preambleLines.push(lines[i])
      i++
    }
    const preamble = preambleLines.join("\n")
    if (binary) {
      hunks.push({ id: ++id, file, header: "(binary)", preamble, body: "", added: 0, removed: 0, binary: true })
      continue
    }
    while (i < lines.length && lines[i].startsWith("@@")) {
      const bodyLines = [lines[i]]
      const header = lines[i]
      i++
      let added = 0
      let removed = 0
      while (i < lines.length && !lines[i].startsWith("@@") && !lines[i].startsWith("diff --git")) {
        if (lines[i].startsWith("+")) added++
        else if (lines[i].startsWith("-")) removed++
        bodyLines.push(lines[i])
        i++
      }
      // Drop the split artifact of the diff's trailing newline: kept, it
      // becomes an empty "context" line that --recount counts and git apply
      // then rejects ("patch does not apply") on the file's last hunk.
      while (bodyLines.length && bodyLines[bodyLines.length - 1] === "") bodyLines.pop()
      hunks.push({ id: ++id, file, header, preamble, body: bodyLines.join("\n"), added, removed, binary: false })
    }
  }
  return hunks
}

const HUNK_HEADER = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/

/**
 * Re-anchors a hunk's new-side start for a patch that leaves earlier hunks of
 * the file out. git apply searches from that start and takes the nearest
 * match, so a start still offset by unselected hunks can land an identical
 * block elsewhere. A zero count means "the line before", as git writes it.
 */
function reanchor(body: string, shift: number): string {
  return body.replace(HUNK_HEADER, (_, a: string, b: string | undefined, _c: string, d: string | undefined) => {
    const oldStart = Number(a)
    const oldCount = b === undefined ? 1 : Number(b)
    const newCount = d === undefined ? 1 : Number(d)
    const start = oldStart + shift + (oldCount === 0 ? 1 : 0) - (newCount === 0 ? 1 : 0)
    return `@@ -${a}${b === undefined ? "" : `,${b}`} +${start}${d === undefined ? "" : `,${d}`} @@`
  })
}

function buildPatch(selected: Hunk[]): string {
  const byFile = new Map<string, { preamble: string; bodies: string[]; shift: number }>()
  for (const h of selected) {
    const cur = byFile.get(h.preamble) ?? { preamble: h.preamble, bodies: [], shift: 0 }
    cur.bodies.push(h.binary ? h.body : reanchor(h.body, cur.shift))
    cur.shift += h.added - h.removed
    byFile.set(h.preamble, cur)
  }
  const parts: string[] = []
  for (const { preamble, bodies } of byFile.values()) {
    parts.push(preamble, ...bodies)
  }
  return parts.join("\n") + "\n"
}

/** Identifies one listing: ids are positions in exactly this diff. */
const listToken = (diff: string) => new Bun.CryptoHasher("sha1").update(diff).digest("hex").slice(0, 12)

function checkPaths(paths: string[], cwd: string): void {
  const root = resolve(cwd)
  for (const p of paths) {
    const full = resolve(root, p)
    if (full !== root && !full.startsWith(root + sep))
      throw new Error(`${p} is outside this session's repository (${root}); run from the repository that holds it.`)
  }
}

export const stage_hunks = tool({
  description:
    "List and stage individual diff hunks deterministically — a reliable replacement for `git add -p`. Call with no selection (or list:true) to enumerate the unstaged hunks with ids and a `token`; call with `hunks` (ids) and/or `include`/`exclude` (regex on hunk text) to stage exactly those via `git apply --cached`. Ids are positions in that listing: pass the same `paths` and its `token` so a changed diff is refused instead of staging the wrong hunks, and list again after every staging. Set denySecrets to refuse staging hunks that contain secrets. Operates on the index only (reversible); never commits. Returns the chosen hunks and the resulting staged stat.",
  args: {
    paths: tool.schema.array(tool.schema.string()).optional().describe("Limit to these files (default: all unstaged changes)."),
    list: tool.schema.boolean().optional().describe("List hunks without staging. Implied when no selection is given."),
    hunks: tool.schema.array(tool.schema.number()).optional().describe("Hunk ids to stage (from the list output)."),
    token: tool.schema.string().optional().describe("The `token` of the listing the ids come from; refuses to stage if the diff changed since."),
    include: tool.schema.string().optional().describe("Stage only hunks whose text matches this regex."),
    exclude: tool.schema.string().optional().describe("Never stage hunks whose text matches this regex."),
    denySecrets: tool.schema.boolean().optional().describe("Scan selected hunks for secrets and refuse to stage if any are found."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const diffArgs = ["diff", "--no-color"]
    if (args.paths?.length) {
      checkPaths(args.paths, cwd)
      diffArgs.push("--", ...args.paths)
    }
    const diff = await runGit(diffArgs, cwd)
    const hunks = parseHunks(diff)
    const token = listToken(diff)

    if (args.list || (!args.hunks?.length && !args.include)) {
      return JSON.stringify(
        {
          mode: "list",
          token,
          count: hunks.length,
          hunks: hunks.map((h) => ({
            id: h.id,
            file: h.file,
            header: h.header,
            added: h.added,
            removed: h.removed,
            binary: h.binary,
            preview: h.body.split("\n").slice(0, 8),
          })),
        },
        null,
        2,
      )
    }

    if (args.token && args.token !== token)
      throw new Error("The diff changed since that listing (different paths, or hunks staged since); list again and use the new ids.")
    let selected = hunks.filter((h) => !h.binary)
    if (args.hunks?.length) {
      const unknown = args.hunks.filter((id) => !hunks.some((h) => h.id === id))
      if (unknown.length) throw new Error(`Unknown hunk id(s): ${unknown.join(", ")}; this listing has ${hunks.length}. List again and use its ids.`)
      const set = new Set(args.hunks)
      selected = selected.filter((h) => set.has(h.id))
    }
    if (args.include) {
      const re = new RegExp(args.include)
      selected = selected.filter((h) => re.test(h.body))
    }
    if (args.exclude) {
      const re = new RegExp(args.exclude)
      selected = selected.filter((h) => !re.test(h.body))
    }
    if (!selected.length) throw new Error("No hunks matched the selection.")

    if (args.denySecrets) {
      const findings = dedupe(scanDiff(buildPatch(selected)))
      if (findings.length) {
        return JSON.stringify({ mode: "blocked", reason: "secret findings in selected hunks", findings }, null, 2)
      }
    }

    await withTempFile("opencode-stage", ".patch", buildPatch(selected), (patch) =>
      runGit(["apply", "--cached", "--recount", "--whitespace=nowarn", patch], cwd),
    )
    const staged = await runGit(["diff", "--cached", "--stat"], cwd)
    return JSON.stringify({ mode: "staged", stagedHunkIds: selected.map((h) => h.id), staged: staged.trim() }, null, 2)
  },
})
