import { tool } from "../define"
import { runGhJson, runGit } from "../exec"
import { resolveRepo } from "./shared"

export const provenance = tool({
  description:
    "Trace a change to its origin: commit -> PR -> Issue. Anchor with a `sha`, with `file` + `lines` (blame), or with `token`/`regex` to pickaxe the commit that introduced a string (anchored on the oldest hit — the introducer; the newest hit is reported alongside). Returns the commit, the pull requests that introduced it (via the GitHub commits/{sha}/pulls API), and the Issues those PRs close, plus link-ready refs (bare short SHA, #PR, #Issue). Read-only; does not run bisect. Local/unpushed commits return no PRs.",
  args: {
    sha: tool.schema.string().optional().describe("Commit SHA to trace. If omitted, provide file + lines, or token/regex."),
    file: tool.schema.string().optional().describe("File to blame (with lines) or to scope a token/regex search."),
    lines: tool.schema.string().optional().describe('Line range for blame, e.g. "10,20" or "10,+5".'),
    token: tool.schema.string().optional().describe("Find the commit that introduced this exact string (pickaxe, git log -S)."),
    regex: tool.schema.string().optional().describe("Find the commit that introduced a match of this regex (git log -G)."),
    repo: tool.schema.string().optional().describe('"owner/repo". Defaults to the current repository.'),
  },
  async execute(args, context) {
    const cwd = context.worktree
    let sha = args.sha?.trim()
    let locatedBy: string | undefined
    let pickaxe: { hits: number; newest?: string; oldest?: string } | undefined
    if (!sha) {
      if (args.file && args.lines) {
        const blame = await runGit(["blame", "-w", "-C", "-L", args.lines, "--porcelain", "--", args.file], cwd)
        sha = blame.split("\n")[0]?.split(" ")[0]
        locatedBy = `blame ${args.file}:${args.lines}`
      } else if (args.token || args.regex) {
        const pick = args.token ? ["-S", args.token] : ["-G", args.regex as string]
        const argv = ["log", ...pick, "--format=%H"]
        if (args.file) argv.push("--", args.file)
        // Oldest hit = the commit that introduced the string; newer hits are
        // later edits or removals of it.
        const hits = (await runGit(argv, cwd)).split("\n").map((s) => s.trim()).filter(Boolean)
        sha = hits[hits.length - 1]
        pickaxe = { hits: hits.length, newest: hits[0]?.slice(0, 8), oldest: sha?.slice(0, 8) }
        locatedBy = `${args.token ? `pickaxe -S "${args.token}"` : `pickaxe -G "${args.regex}"`} (oldest of ${hits.length} hit(s))`
      } else {
        throw new Error("Provide `sha`, `file` + `lines`, or `token`/`regex`.")
      }
      if (!sha || !/^[0-9a-f]{7,40}$/.test(sha)) throw new Error("Could not locate a commit from the given anchor.")
    }
    const { full } = await resolveRepo(args.repo, cwd)
    const meta = (await runGit(["show", "-s", "--format=%H%n%s%n%an%n%aI", sha], cwd)).split("\n")
    const commit = { sha: meta[0] ?? sha, subject: meta[1] ?? "", author: meta[2] ?? "", date: meta[3] ?? "" }
    let pulls: any[] = []
    try {
      pulls = (await runGhJson(["api", `repos/${full}/commits/${sha}/pulls`, "--jq", "[.[]|{number,title,state}]"], cwd)) ?? []
    } catch {
      pulls = []
    }
    const issues: any[] = []
    for (const pr of pulls) {
      try {
        const v = await runGhJson(
          ["pr", "view", String(pr.number), "--json", "closingIssuesReferences", "--jq", "[.closingIssuesReferences[]?|{number,title}]"],
          cwd,
        )
        for (const is of v ?? []) issues.push({ ...is, viaPR: pr.number })
      } catch {
        // PR not resolvable; skip
      }
    }
    const links = {
      commit: commit.sha.slice(0, 8),
      prs: pulls.map((p: any) => `#${p.number}`),
      issues: issues.map((i: any) => `#${i.number}`),
    }
    return JSON.stringify({ commit, locatedBy, pickaxe, repo: full, pulls, issues, links }, null, 2)
  },
})
