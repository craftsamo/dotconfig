import { runGh } from "../exec"

export async function resolveRepo(repo: string | undefined, cwd?: string): Promise<{ full: string }> {
  const r = (repo ?? "").trim()
  if (r.includes("/")) return { full: r }
  const full = (await runGh(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"], cwd)).trim()
  return { full }
}

export async function fileExists(cwd: string, rel: string): Promise<boolean> {
  try {
    return await Bun.file(`${cwd}/${rel}`).exists()
  } catch {
    return false
  }
}
