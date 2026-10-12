import { existsSync, readFileSync, realpathSync, statSync } from "fs"
import { homedir } from "os"
import { basename, extname, isAbsolute, resolve } from "path"

/**
 * Images and videos `gh pr create/edit --attach` uploads into a PR body
 * (gh >= 2.99.0). The upload happens after the push and cannot be deleted,
 * so every file is checked here, in the preview, against the limits gh itself
 * applies, and pinned by its content hash; the publication checks the hash
 * again right before each gh call. That is best effort, not a guarantee:
 * gh reads the file a moment after the last check.
 *
 * Paths are passed to gh absolute. gh matches a body reference such as
 * `![alt](./shot.png)` by resolving it against its own working directory —
 * the worktree — so a reference relative to the worktree root, or an
 * absolute one, is rewritten to the uploaded URL; any other file is appended.
 */

export const ATTACH_MIN_GH = [2, 99, 0] as const
const MAX_PER_PR = 50
const MiB = 1024 * 1024
const IMAGE_MAX = 10 * MiB
const VIDEO_MAX = 100 * MiB
const VIDEO_FREE_MAX = 10 * MiB
const KINDS: Record<string, "image" | "video"> = {
  ".png": "image",
  ".jpg": "image",
  ".jpeg": "image",
  ".gif": "image",
  ".webp": "image",
  ".svg": "image",
  ".mp4": "video",
  ".mov": "video",
  ".webm": "video",
}

export type AttachmentRequest = { branch: string; path: string; alt?: string }
export type Attachment = { branch: string; path: string; alt: string | null; kind: "image" | "video"; bytes: number; sha256: string }
type Refusal = { rule: string; message: string }

/** The `--attach` arguments for one branch: `<absolute path>[#alt]`, the form gh parses. */
export const attachArgs = (list: Attachment[], branch: string) =>
  list.filter((a) => a.branch === branch).map((a) => `--attach=${a.alt ? `${a.path}#${a.alt}` : a.path}`)

const sha256 = (path: string) => new Bun.CryptoHasher("sha256").update(readFileSync(path)).digest("hex")

/**
 * Why one branch's files can no longer be uploaded as the preview pinned them:
 * different bytes, or a file that now shadows one. Run it right before the gh
 * call; gh reads the files a moment later, a window this cannot close.
 */
export function unsafeNow(list: Attachment[], branch: string): string[] {
  const out: string[] = []
  for (const a of list.filter((x) => x.branch === branch)) {
    let same = false
    try {
      same = sha256(a.path) === a.sha256
    } catch {}
    if (!same) out.push(`${a.path} changed since the preview`)
    const shadow = a.alt ? shadowedBy(a.path, a.alt) : null
    if (shadow) out.push(`gh would now read ${shadow} instead of ${a.path}`)
  }
  return out
}

/**
 * gh takes `<path>#<alt>` as the longest existing file it can find: the whole
 * argument, else the part before each `#` from the last one back. Any such
 * file longer than the intended path would be uploaded instead of it.
 */
function shadowedBy(path: string, alt: string): string | null {
  const arg = `${path}#${alt}`
  if (existsSync(arg)) return arg
  for (let i = alt.lastIndexOf("#"); i >= 0; i = i ? alt.lastIndexOf("#", i - 1) : -1) {
    const candidate = `${path}#${alt.slice(0, i)}`
    if (existsSync(candidate)) return candidate
  }
  return null
}

/** `gh version X.Y.Z` → whether it is at least ATTACH_MIN_GH; null when unreadable. */
export function ghSupportsAttach(versionOutput: string | null): { version: string | null; ok: boolean | null } {
  const m = versionOutput?.match(/gh version (\d+)\.(\d+)\.(\d+)/)
  if (!m) return { version: null, ok: null }
  const have = [Number(m[1]), Number(m[2]), Number(m[3])]
  for (let i = 0; i < 3; i++) if (have[i] !== ATTACH_MIN_GH[i]) return { version: have.join("."), ok: have[i] > ATTACH_MIN_GH[i] }
  return { version: have.join("."), ok: true }
}

const expand = (cwd: string, p: string) => {
  const path = p === "~" ? homedir() : p.startsWith("~/") ? resolve(homedir(), p.slice(2)) : p
  return isAbsolute(path) ? resolve(path) : resolve(cwd, path)
}

const size = (n: number) => (n >= MiB ? `${(n / MiB).toFixed(1)} MiB` : `${Math.ceil(n / 1024)} KiB`)

/**
 * Check the requested attachments of the layers being published. `branches`
 * are the active layers; naming another branch is the caller's mistake and
 * throws, like layer metadata. Problems with the files themselves, the gh
 * version or the repository come back as refusals, so the preview shows them.
 */
export function checkAttachments(
  cwd: string,
  requests: AttachmentRequest[],
  layers: { branch: string; pr: { number: number } | null }[],
  env: { ghVersion: string | null; visibility: string | null },
) {
  const list: Attachment[] = []
  const refusals: Refusal[] = []
  const warnings: string[] = []
  if (!requests.length) return { list, refusals, warnings, info: null }

  const known = new Set(layers.map((l) => l.branch))
  for (const r of requests) if (!known.has(r.branch)) throw new Error(`${r.branch} is not being published here (${[...known].join(", ")}).`)

  const gh = ghSupportsAttach(env.ghVersion)
  if (gh.ok === null) refusals.push({ rule: "attachments", message: `Could not read the gh version; attaching needs gh ${ATTACH_MIN_GH.join(".")} or later.` })
  else if (!gh.ok) refusals.push({ rule: "attachments", message: `gh ${gh.version} cannot attach files; upgrade to ${ATTACH_MIN_GH.join(".")} or later (brew upgrade gh).` })

  const seen = new Map<string, Set<string>>()
  for (const r of requests) {
    const shown = r.path.trim()
    if (!shown) {
      refusals.push({ rule: "attachments", message: `An attachment for ${r.branch} names no file.` })
      continue
    }
    const path = expand(cwd, shown)
    const kind = KINDS[extname(path).toLowerCase()]
    const alt = r.alt?.trim() || null
    let stat
    try {
      stat = statSync(path)
    } catch {
      refusals.push({ rule: "attachments", message: `${shown} does not exist.` })
      continue
    }
    if (!stat.isFile()) refusals.push({ rule: "attachments", message: `${shown} is not a regular file.` })
    else if (!stat.size) refusals.push({ rule: "attachments", message: `${shown} is empty.` })
    else if (!kind) refusals.push({ rule: "attachments", message: `${shown} is not an image or video gh attaches (${Object.keys(KINDS).join(", ")}).` })
    else if (kind === "image" && stat.size > IMAGE_MAX) refusals.push({ rule: "attachments", message: `${shown} is ${size(stat.size)}; images must be at most 10 MiB.` })
    else if (kind === "video" && stat.size > VIDEO_MAX) refusals.push({ rule: "attachments", message: `${shown} is ${size(stat.size)}; videos must be at most 100 MiB.` })
    else if (kind === "video" && alt) refusals.push({ rule: "attachments", message: `${shown} is a video, which renders as a player and takes no alt text.` })
    else if (alt && shadowedBy(path, alt))
      refusals.push({ rule: "attachments", message: `gh would read ${shadowedBy(path, alt)} instead of ${shown}, since its alt text starts a longer file name; change the alt text.` })
    else {
      const real = realpathSync(path)
      const mine = seen.get(r.branch) ?? new Set<string>()
      seen.set(r.branch, mine)
      if (mine.has(real)) {
        refusals.push({ rule: "attachments", message: `${shown} is attached to ${r.branch} twice; each file once.` })
        continue
      }
      mine.add(real)
      if (kind === "video" && stat.size > VIDEO_FREE_MAX)
        warnings.push(`${shown} is ${size(stat.size)}; videos over 10 MiB upload only to repositories of paid plans.`)
      list.push({ branch: r.branch, path, alt, kind, bytes: stat.size, sha256: sha256(path) })
    }
  }
  for (const [branch, files] of seen) if (files.size > MAX_PER_PR) refusals.push({ rule: "attachments", message: `${branch} has ${files.size} attachments; gh takes at most ${MAX_PER_PR} per PR.` })

  for (const l of layers)
    if (l.pr && list.some((a) => a.branch === l.branch))
      warnings.push(
        `${l.branch} already has PR #${l.pr.number}: its attachments go into the body \`prs\` gives it, else are appended to its current body; publishing again uploads and appends them again.`,
      )

  const visibility = env.visibility?.toUpperCase() ?? null
  const audience =
    visibility === "PUBLIC"
      ? "The repository is public: anyone, signed in or not, can open the uploaded files."
      : visibility === "PRIVATE" || visibility === "INTERNAL"
        ? `The repository is ${visibility.toLowerCase()}: only people with access to it can open the uploaded files.`
        : "The repository's visibility could not be read; treat the uploaded files as public."
  return {
    list,
    refusals,
    warnings,
    info: {
      layers: layers
        .filter((l) => list.some((a) => a.branch === l.branch))
        .map((l) => ({
          branch: l.branch,
          pr: l.pr?.number ?? null,
          files: list.filter((a) => a.branch === l.branch).map((a) => ({ path: a.path, name: basename(a.path), kind: a.kind, size: size(a.bytes), alt: a.alt })),
        })),
      visibility,
      note: `${audience} Uploads cannot be deleted, and the secret scan does not read images: show the user each file before publishing. A body reference to a file (\`![alt](./shot.png)\` relative to the worktree root, or its absolute path) is replaced by the uploaded URL; other files are appended to the body.`,
    },
  }
}
