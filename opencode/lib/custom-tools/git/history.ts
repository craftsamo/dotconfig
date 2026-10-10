import { tool } from "../define"
import { runGhJson, tryGit } from "../exec"
import { fileExists } from "./shared"

export const history_digest = tool({
  description:
    "Gather signals for inferring a repository's commit and PR conventions: recent commit subjects with conventional-commit type/scope frequencies, presence of commitlint / .gitmessage / commitizen / CONTRIBUTING config, recent merged PR titles, and whether a PR template exists. Read-only — the inference itself stays a judgment step in the skills.",
  args: {
    limit: tool.schema.number().optional().describe("How many recent non-merge commits to sample (default 30)."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const limit = args.limit ?? 30
    // Tolerate an unborn HEAD (no commits yet): report an empty sample.
    const logRes = await tryGit(["log", "--no-merges", `-${limit}`, "--pretty=%s"], cwd)
    const subjects = logRes.ok ? logRes.stdout.split("\n").filter(Boolean) : []
    const typeFrequency: Record<string, number> = {}
    const scopes = new Set<string>()
    let conventional = 0
    for (const s of subjects) {
      const m = s.match(/^(\w+)(?:\(([^)]+)\))?!?:\s/)
      if (m) {
        conventional++
        typeFrequency[m[1]] = (typeFrequency[m[1]] ?? 0) + 1
        if (m[2]) scopes.add(m[2])
      }
    }
    const configCandidates = [
      "commitlint.config.js",
      "commitlint.config.cjs",
      "commitlint.config.mjs",
      "commitlint.config.ts",
      ".commitlintrc",
      ".commitlintrc.json",
      ".commitlintrc.js",
      ".commitlintrc.yml",
      ".commitlintrc.yaml",
      ".gitmessage",
      ".czrc",
      ".cz.json",
      "cz.config.js",
      "CONTRIBUTING.md",
      ".github/CONTRIBUTING.md",
    ]
    const commitConfigFiles: string[] = []
    for (const c of configCandidates) if (await fileExists(cwd, c)) commitConfigFiles.push(c)

    const prTemplateCandidates = [
      ".github/PULL_REQUEST_TEMPLATE.md",
      ".github/pull_request_template.md",
      "PULL_REQUEST_TEMPLATE.md",
      "docs/PULL_REQUEST_TEMPLATE.md",
    ]
    let prTemplate: string | null = null
    for (const c of prTemplateCandidates)
      if (await fileExists(cwd, c)) {
        prTemplate = c
        break
      }

    let prTitles: string[] = []
    try {
      prTitles = (await runGhJson(["pr", "list", "--state", "merged", "--limit", "15", "--json", "title", "--jq", "[.[].title]"], cwd)) ?? []
    } catch {
      // gh unavailable / no network
    }

    return JSON.stringify(
      {
        commitSampleSize: subjects.length,
        conventionalRatio: subjects.length ? +(conventional / subjects.length).toFixed(2) : 0,
        typeFrequency,
        scopes: [...scopes],
        commitConfigFiles,
        commitSubjects: subjects.slice(0, 15),
        prTitles,
        prTemplate,
      },
      null,
      2,
    )
  },
})
