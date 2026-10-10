import { tool } from "./define"
import { exec, runGhJson } from "./exec"

/**
 * GitHub pull-request status. Read-only: it never pushes, comments, reruns or
 * merges. Waiting happens inside the tool, so a caller gets one final state
 * instead of `sleep` + `gh pr checks` loops or the full table `--watch`
 * reprints on every refresh.
 */

type Bucket = "pass" | "fail" | "pending" | "skipping" | "cancel"
type Check = { name: string; workflow: string | null; bucket: Bucket; state: string; url: string | null }

const VIEW_FIELDS = [
  "number",
  "title",
  "url",
  "state",
  "isDraft",
  "baseRefName",
  "headRefName",
  "headRefOid",
  "mergeable",
  "mergeStateStatus",
  "reviewDecision",
  "closingIssuesReferences",
  "statusCheckRollup",
  "latestReviews",
].join(",")

// Jobs that only gate on the others; their own log says nothing about the failure.
const AGGREGATE_JOB = /\b(required|all)[ _-]?(checks?|jobs?)\b|\bci[ _-]?(success|ok|status)\b/i

/** CheckRun (Actions, apps) and StatusContext (commit statuses) in one shape. */
export function normalizeCheck(c: any): Check {
  if (c?.__typename === "StatusContext" || ("context" in (c ?? {}) && !("conclusion" in (c ?? {})))) {
    const state = String(c.state ?? "")
    const bucket: Bucket = state === "SUCCESS" ? "pass" : state === "FAILURE" || state === "ERROR" ? "fail" : "pending"
    return { name: String(c.context ?? ""), workflow: null, bucket, state, url: c.targetUrl ?? null }
  }
  const status = String(c.status ?? "")
  const conclusion = String(c.conclusion ?? "")
  let bucket: Bucket = "pending"
  if (status === "COMPLETED") {
    if (conclusion === "SUCCESS") bucket = "pass"
    else if (conclusion === "SKIPPED" || conclusion === "NEUTRAL") bucket = "skipping"
    else if (conclusion === "CANCELLED") bucket = "cancel"
    else bucket = "fail"
  }
  return { name: String(c.name ?? ""), workflow: c.workflowName || null, bucket, state: conclusion || status, url: c.detailsUrl ?? null }
}

export function overall(checks: Check[]): "no_checks" | "pending" | "fail" | "pass" {
  if (!checks.length) return "no_checks"
  if (checks.some((c) => c.bucket === "fail")) return "fail"
  if (checks.some((c) => c.bucket === "pending")) return "pending"
  return "pass"
}

/** Resolves after `ms`, or as soon as `signal` aborts. */
function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal?.aborted) return resolve()
    const timer = setTimeout(done, ms)
    function done() {
      clearTimeout(timer)
      signal?.removeEventListener("abort", done)
      resolve()
    }
    signal?.addEventListener("abort", done, { once: true })
  })
}

const repoOf = (url: string) => url.match(/github\.com\/([^/]+\/[^/]+)\/pull\//)?.[1] ?? null

async function failedLogs(failed: Check[], repo: string, lines: number, cwd: string) {
  const jobs = failed
    .map((c) => ({ check: c, job: c.url?.match(/\/actions\/runs\/\d+\/job\/(\d+)/)?.[1] }))
    .filter((j): j is { check: Check; job: string } => Boolean(j.job))
  const real = jobs.filter((j) => !AGGREGATE_JOB.test(j.check.name))
  const out = []
  for (const { check, job } of (real.length ? real : jobs).slice(0, 3)) {
    const res = await exec(["gh", "run", "view", "--job", job, "--log-failed", "--repo", repo], { cwd })
    const log = res.stdout.split("\n").map((l) => l.replace(/^[^\t]*\t[^\t]*\t/, ""))
    out.push({
      name: check.name,
      job,
      url: check.url,
      errors: log.filter((l) => /##\[error\]/.test(l)).slice(0, 10).map((l) => l.trim()),
      tail: log.filter((l) => l.trim()).slice(-lines).join("\n"),
    })
  }
  return out
}

async function unresolvedThreads(repo: string, number: number, cwd: string) {
  const [owner, name] = repo.split("/")
  const query = `query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewThreads(first:100){nodes{isResolved isOutdated path line comments(first:1){nodes{author{login} body url}}}}}}}`
  try {
    const data = await runGhJson(
      ["api", "graphql", "-f", `query=${query}`, "-F", `owner=${owner}`, "-F", `name=${name}`, "-F", `number=${number}`],
      cwd,
    )
    const nodes = data?.data?.repository?.pullRequest?.reviewThreads?.nodes ?? []
    return nodes
      .filter((t: any) => !t.isResolved)
      .map((t: any) => {
        const c = t.comments?.nodes?.[0] ?? {}
        return { path: t.path, line: t.line, outdated: Boolean(t.isOutdated), author: c.author?.login ?? null, body: String(c.body ?? "").slice(0, 300), url: c.url ?? null }
      })
  } catch {
    return null
  }
}

export const pr_status = tool({
  description:
    "Where a pull request stands, in one read-only call: state and draft flag, head sha, mergeable / mergeStateStatus, review decision, closing issues, every check normalized to pass / fail / pending / skipping / cancel with an overall verdict, the failed jobs' `##[error]` lines and log tails (skipping aggregate gate jobs), latest reviews and unresolved review threads. With wait:true it polls inside the tool until the checks settle, a check fails, or the timeout: checks that are not registered yet right after a push count as pending for a grace period, and an UNKNOWN merge state is re-read. Never pushes, comments, reruns or merges.",
  args: {
    pr: tool.schema.string().optional().describe("PR number, URL or branch. Defaults to the current branch's PR."),
    repo: tool.schema.string().optional().describe('"owner/repo". Defaults to the current repository.'),
    wait: tool.schema.boolean().optional().describe("Poll until the checks settle (default false)."),
    timeoutSec: tool.schema.number().optional().describe("Longest wait in seconds (default 600, at most 1800)."),
    intervalSec: tool.schema.number().optional().describe("Seconds between polls (default 20)."),
    noChecksGraceSec: tool.schema.number().optional().describe("How long missing checks count as pending while waiting (default 180)."),
    failFast: tool.schema.boolean().optional().describe("Stop waiting at the first failed check (default true)."),
    logLines: tool.schema.number().optional().describe("Log lines kept per failed job (default 80; 0 skips logs)."),
    reviews: tool.schema.boolean().optional().describe("Include reviews and unresolved threads (default true)."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const argv = ["pr", "view", ...(args.pr ? [args.pr] : []), "--json", VIEW_FIELDS, ...(args.repo ? ["--repo", args.repo] : [])]
    const timeout = Math.min(Math.max(args.timeoutSec ?? 600, 0), 1800) * 1000
    const interval = Math.max(args.intervalSec ?? 20, 1) * 1000
    const grace = Math.max(args.noChecksGraceSec ?? 180, 0) * 1000
    const failFast = args.failFast ?? true
    const started = Date.now()
    let polls = 0
    let view: any
    let checks: Check[]
    let verdict: ReturnType<typeof overall>
    let endedBy: "not_waiting" | "complete" | "timeout" | "no_checks" | "failed"
    for (;;) {
      view = await runGhJson(argv, cwd)
      polls++
      checks = (view?.statusCheckRollup ?? []).map(normalizeCheck)
      verdict = overall(checks)
      if (!args.wait) {
        endedBy = "not_waiting"
        break
      }
      const elapsed = Date.now() - started
      const unsettledMerge = view?.state === "OPEN" && view?.mergeStateStatus === "UNKNOWN"
      if (verdict === "fail" && failFast) {
        endedBy = "failed"
        break
      }
      if (verdict === "no_checks" && elapsed >= grace) {
        endedBy = "no_checks"
        break
      }
      if (verdict !== "no_checks" && !checks.some((c) => c.bucket === "pending") && !unsettledMerge) {
        endedBy = "complete"
        break
      }
      if (elapsed + interval > timeout) {
        endedBy = "timeout"
        break
      }
      await sleep(interval, context.signal)
      if (context.signal?.aborted) throw new Error("Stopped while waiting for the checks.")
    }

    const repo = args.repo ?? repoOf(String(view.url ?? "")) ?? ""
    const counts = { pass: 0, fail: 0, pending: 0, skipping: 0, cancel: 0 }
    for (const c of checks) counts[c.bucket]++
    const failed = checks.filter((c) => c.bucket === "fail")
    const logLines = args.logLines ?? 80
    const hints: string[] = []
    if (verdict === "no_checks") {
      if (view.mergeable === "CONFLICTING") hints.push("The PR conflicts with its base; GitHub does not run pull_request workflows until the conflict is resolved.")
      else {
        const runs = await exec(["gh", "run", "list", "--branch", view.headRefName, "--limit", "1", "--json", "databaseId", "--repo", repo], { cwd })
        if (runs.ok && runs.stdout.trim() === "[]") hints.push("No workflow run exists for this branch; the repository may have no CI for it, or runs await approval.")
      }
    }
    if (view.mergeStateStatus === "UNKNOWN") hints.push("GitHub is still computing mergeability; read it again shortly.")

    const reviewsWanted = args.reviews ?? true
    return JSON.stringify(
      {
        pr: {
          number: view.number,
          title: view.title,
          url: view.url,
          state: view.state,
          isDraft: view.isDraft,
          base: view.baseRefName,
          head: view.headRefName,
          headSha: view.headRefOid,
        },
        mergeable: view.mergeable,
        mergeStateStatus: view.mergeStateStatus,
        reviewDecision: view.reviewDecision || null,
        closingIssues: (view.closingIssuesReferences ?? []).map((i: any) => i.number),
        checks: { overall: verdict, counts, items: checks },
        failedLogs: failed.length && logLines > 0 && repo ? await failedLogs(failed, repo, logLines, cwd) : [],
        reviews: reviewsWanted
          ? (view.latestReviews ?? []).map((r: any) => ({ author: r.author?.login ?? null, state: r.state, body: String(r.body ?? "").slice(0, 300) }))
          : null,
        unresolvedThreads: reviewsWanted && repo ? await unresolvedThreads(repo, view.number, cwd) : null,
        waited: { seconds: Math.round((Date.now() - started) / 1000), polls, endedBy },
        hints,
      },
      null,
      2,
    )
  },
})
