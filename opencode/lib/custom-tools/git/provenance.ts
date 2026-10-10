import { tool } from "../define"
import { runGhJson, runGit, tryGit } from "../exec"
import { resolveRepo } from "./shared"

type Commit = { sha: string; subject: string; author: string; date: string; source: "local" | "github" }

/** The commit from this clone when it has it, else from GitHub (another repository, or not fetched). */
async function readCommit(sha: string, repo: string, cwd: string): Promise<Commit> {
  if ((await tryGit(["cat-file", "-e", `${sha}^{commit}`], cwd)).ok) {
    const meta = (await runGit(["show", "-s", "--format=%H%n%s%n%an%n%aI", sha], cwd)).split("\n")
    return { sha: meta[0] ?? sha, subject: meta[1] ?? "", author: meta[2] ?? "", date: meta[3] ?? "", source: "local" }
  }
  let remote: any = null
  try {
    remote = await runGhJson(
      ["api", `repos/${repo}/commits/${sha}`, "--jq", '{sha: .sha, subject: (.commit.message | split("\\n")[0]), author: .commit.author.name, date: .commit.author.date}'],
      cwd,
    )
  } catch {
    // not on GitHub either
  }
  if (!remote?.sha) throw new Error(`Commit ${sha} is neither in this clone (${cwd}) nor in ${repo} on GitHub.`)
  return { sha: remote.sha, subject: remote.subject ?? "", author: remote.author ?? "", date: remote.date ?? "", source: "github" }
}

export const provenance = tool({
  description:
    "Trace a change to its origin: commit -> PR -> Issue. Anchor with a `sha`, with `file` + `lines` (blame), or with `token`/`regex` to pickaxe the commit that introduced a string (anchored on the oldest hit — the introducer; the newest hit is reported alongside). Returns the commit, the pull requests that introduced it (via the GitHub commits/{sha}/pulls API), and the Issues those PRs close, plus link-ready refs (bare short SHA, #PR, #Issue). A `sha` of another repository (`repo`) or one this clone lacks is read from GitHub; blame and pickaxe need the session to run in a clone of that repository. Read-only; does not run bisect. Local/unpushed commits return no PRs.",
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
      const anchored = Boolean((args.file && args.lines) || args.token || args.regex)
      const wanted = args.repo?.trim()
      if (anchored && wanted?.includes("/")) {
        let local = ""
        try {
          local = (await resolveRepo(undefined, cwd)).full
        } catch {
          // not a GitHub clone; the anchor below reads it as is
        }
        if (local && local.toLowerCase() !== wanted.toLowerCase())
          throw new Error(`blame and pickaxe read the local clone, which is ${local}, not ${wanted}. Run from a clone of ${wanted}, or pass the commit as \`sha\`.`)
      }
      if (args.file && args.lines) {
        const blame = await runGit(["blame", "-w", "-C", "-L", args.lines, "--porcelain", "--", args.file], cwd)
        sha = blame.split("\n")[0]?.split(" ")[0]
        locatedBy = `blame ${args.file}:${args.lines}`
        if (sha && /^0+$/.test(sha)) throw new Error(`${args.file}:${args.lines} starts with a line that is not committed yet; it has no origin to trace.`)
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
    } else if (/^0+$/.test(sha)) {
      throw new Error("An all-zero sha stands for uncommitted changes; there is no commit to trace.")
    }
    const { full } = await resolveRepo(args.repo, cwd)
    const commit = await readCommit(sha, full, cwd)
    let pulls: any[] = []
    try {
      pulls = (await runGhJson(["api", `repos/${full}/commits/${commit.sha}/pulls`, "--jq", "[.[]|{number,title,state}]"], cwd)) ?? []
    } catch {
      pulls = []
    }
    const issues: any[] = []
    for (const pr of pulls) {
      try {
        const v = await runGhJson(
          ["pr", "view", String(pr.number), "--json", "closingIssuesReferences", "--jq", "[.closingIssuesReferences[]?|{number,title}]", "--repo", full],
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
