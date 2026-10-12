import { execFile } from "node:child_process"
import { readFileSync } from "node:fs"
import {
  allocateHermes,
  checkpointFor,
  cycleOf,
  grantsFor,
  ledger,
  PACE_DAYS,
  startOfDay,
  statsDays,
  summarize,
  when,
  ymd,
  type Checkpoint,
  type Lane,
  type StatsModel,
  type Summary,
} from "./core"
import {
  expandHome,
  hermesSince,
  readHermes,
  type HermesUsage,
} from "./hermes"
import { readState, updateState, type State } from "./state"

export type Config = {
  lanes: Lane[]
  // Hermes spends the same orgs: where its profiles live, and the order its
  // credential pool draws the lanes in.
  hermes?: { root: string; order: string[] }
}

export function loadConfig(): Config {
  const file = new URL("./lanes.json", import.meta.url)
  return JSON.parse(readFileSync(file, "utf8")) as Config
}

export function loadLanes(): Lane[] {
  return loadConfig().lanes
}

export type RunStats = (days: number) => Promise<StatsModel[]>

// `opencode stats` asks the running service for an aggregate, which takes about
// a second. Never read the history database from here: it is tens of GB.
export const runStats: RunStats = (days) =>
  new Promise((resolve, reject) =>
    execFile(
      process.env.OPENCODE_BIN || "opencode",
      ["stats", "--days", String(days), "--full", "--json"],
      { maxBuffer: 64 * 1024 * 1024, timeout: 30_000 },
      (error, stdout) => {
        if (error) return reject(error)
        try {
          resolve(
            (JSON.parse(stdout) as { models?: StatsModel[] }).models ?? [],
          )
        } catch (cause) {
          reject(cause)
        }
      },
    ),
  )

export type Sources = {
  stats: RunStats
  // Undefined when Hermes is not configured or cannot be read.
  hermes: () => Promise<HermesUsage | undefined>
  clock: () => Date
  load: () => State
  // Read, change and write the state as one step (see state.ts).
  update: <T>(fn: (state: State) => Promise<T> | T) => Promise<T>
}

export function sources(config: Config): Sources {
  return {
    stats: runStats,
    hermes: async () =>
      config.hermes
        ? readHermes(expandHome(config.hermes.root)).catch(() => undefined)
        : undefined,
    clock: () => new Date(),
    load: () => readState(),
    update: (fn) => updateState(fn),
  }
}

// Neither org has a payment method, so the Console stops requests at about
// zero: an estimate well below it means a grant arrived that nobody listed. The
// margin covers cost accounting that runs a little ahead of the Console's.
export const INFER_MARGIN = 5
export const INFER_SHARE = 0.1

type Context = {
  config: Config
  now: Date
  stats: RunStats
  hermes: HermesUsage | undefined
}

async function context(
  now: Date,
  config: Config,
  src: Sources,
): Promise<Context> {
  const runs = new Map<number, Promise<StatsModel[]>>()
  return {
    config,
    now,
    stats: (days) => {
      if (!runs.has(days)) runs.set(days, src.stats(days))
      return runs.get(days)!
    },
    hermes: await src.hermes(),
  }
}

// A checkpoint is written only from a consistent reading. `opencode stats`
// counts whole local days, so a run that crossed midnight mixes two days'
// baselines; and a missing Hermes reading would leave its spend out of a
// balance carried forward for good.
function writable(ctx: Context, src: Sources): string | undefined {
  if (ymd(src.clock()) !== ymd(ctx.now)) return "the day changed during the reading"
  if (ctx.config.hermes && !ctx.hermes) return "Hermes usage could not be read"
  return undefined
}

// Another writer wrote after this reading began: its baselines may be newer
// than this reading's figures, and writing over them would count spend twice.
const overtaken = (base: State, state: State) => state.revision !== base.revision

// `stats --days PACE_DAYS` covers the days before today and today so far.
export const paceWindow = (now: Date) =>
  (now.getTime() -
    startOfDay(new Date(now.getFullYear(), now.getMonth(), now.getDate() - (PACE_DAYS - 1))).getTime()) /
  86_400_000

const own = (models: StatsModel[], provider: string) =>
  models.filter((m) => m.model.providerID === provider)
const total = (models: StatsModel[]) =>
  models.reduce((sum, m) => sum + m.cost, 0)
// In cents, as the Console shows it.
const cents = (n: number) => Math.round(n * 100) / 100

async function compute(ctx: Context, state: State): Promise<Summary[]> {
  const order = ctx.config.hermes?.order ?? []
  const rows = []
  for (const lane of ctx.config.lanes) {
    const ls = state.lanes[lane.provider] ?? { grants: [] }
    const grants = grantsFor(lane, ls, ctx.now)
    const checkpoint = checkpointFor(lane, ls, grants, ctx.now)
    const at = when(checkpoint.at)
    const mine = own(
      await ctx.stats(statsDays(when(checkpoint.opencodeFrom), ctx.now)),
      lane.provider,
    )
    const opencode = Math.max(0, total(mine) - checkpoint.opencodeBase)
    const recent = own(await ctx.stats(PACE_DAYS), lane.provider)
    const hermesCounted =
      ctx.hermes !== undefined &&
      checkpoint.hermes !== undefined &&
      order.includes(lane.provider)
    const byId = new Map<string, number>()
    for (const m of recent)
      byId.set(m.model.id, (byId.get(m.model.id) ?? 0) + m.cost)
    rows.push({
      lane,
      grants,
      checkpoint,
      opencode,
      opencodeWindow: { from: checkpoint.opencodeFrom, total: total(mine) },
      opencodePerDay: total(recent) / paceWindow(ctx.now),
      hermesCounted,
      window: hermesCounted ? hermesSince(ctx.hermes!, checkpoint.hermes!) : 0,
      room: ledger(grants, at, checkpoint.balance, opencode, ctx.now).available,
      byModel: [...byId.entries()]
        .map(([id, cost]) => ({ id, cost }))
        .sort((a, b) => b.cost - a.cost),
    })
  }
  const counted = rows.filter((r) => r.hermesCounted)
  const charged = allocateHermes(
    order,
    Object.fromEntries(counted.map((r) => [r.lane.provider, r.window])),
    Object.fromEntries(counted.map((r) => [r.lane.provider, r.room])),
  )
  return rows.map((r) =>
    summarize(
      r.lane,
      { ...r, hermes: charged[r.lane.provider] ?? 0 },
      ctx.now,
    ),
  )
}

// Every lane gets a new checkpoint at once: `given` for the lane it names, the
// current estimate carried forward (`rolled`) for the others, all on one
// Hermes baseline. Hermes' spend is split between lanes by their windows since
// their checkpoints, so a lane re-based alone would drop what the other lane
// had been charged. A carried estimate keeps the stats window it was computed
// from, so its baseline is that same run's cost and no spend falls between.
async function rebase(
  ctx: Context,
  state: State,
  summaries: Summary[],
  given?: { provider: string; balance: number; source: "console" | "empty" },
): Promise<void> {
  const today = await ctx.stats(1)
  for (const s of summaries) {
    const provider = s.lane.provider
    const mine = given?.provider === provider ? given : undefined
    const window =
      !mine && s.opencodeWindow
        ? s.opencodeWindow
        : { from: ymd(ctx.now), total: total(own(today, provider)) }
    const checkpoint: Checkpoint = {
      at: ctx.now.toISOString(),
      // A carried estimate below zero is cost accounting running ahead (any
      // more would have inferred a grant): the Console stops near zero, and
      // carrying a debt would turn the tolerated gap into an inferred grant.
      balance: cents(mine ? mine.balance : Math.max(0, s.remaining)),
      source: mine ? mine.source : "rolled",
      opencodeFrom: window.from,
      opencodeBase: window.total,
      ...(ctx.hermes ? { hermes: ctx.hermes } : {}),
    }
    const ls = (state.lanes[provider] ??= { grants: [] })
    ls.checkpoint = checkpoint
    // An empty balance also proves no unlisted grant is live.
    ls.grants = ls.grants.filter(
      (g) =>
        when(g.expires) > ctx.now &&
        !(mine?.source === "empty" && g.source === "inferred"),
    )
  }
}

const inferable = (s: Summary) =>
  s.remaining <
  -Math.max(INFER_MARGIN, INFER_SHARE * (s.spent.opencode + s.spent.hermes))

// Writes what the estimate has learned: a grant that must have arrived, or a
// grant that expired since the checkpoint (every lane is re-based, so later
// spend is no longer charged to it). Grants first, so a re-base carries them.
async function settle(
  ctx: Context,
  state: State,
  summaries: Summary[],
): Promise<boolean> {
  let inferred = false
  for (const s of summaries) {
    if (!inferable(s)) continue
    const { lane } = s
    const ls = (state.lanes[lane.provider] ??= { grants: [] })
    const latest = Math.max(
      ctx.now.getTime(),
      ...s.grants.map((g) => when(g.expires).getTime()),
    )
    const expires = ymd(cycleOf(lane.renewalDay, new Date(latest)).end)
    if (ls.grants.some((g) => ymd(when(g.expires)) === expires)) continue
    ls.grants.push({
      amount: lane.amount,
      granted: ctx.now.toISOString(),
      expires,
      source: "inferred",
    })
    inferred = true
  }
  if (inferred) return true
  if (!summaries.some((s) => s.grants.some((g) => g.expired))) return false
  await rebase(ctx, state, summaries)
  return true
}

const needsSettling = (summaries: Summary[]) =>
  summaries.some((s) => inferable(s) || s.grants.some((g) => g.expired))

export async function collect(
  now?: Date,
  config = loadConfig(),
  src: Sources = sources(config),
): Promise<Summary[]> {
  // Read before any figure is fetched, so a later write shows as overtaking.
  const base = src.load()
  const ctx = await context(now ?? src.clock(), config, src)
  const summaries = await compute(ctx, base)
  if (!needsSettling(summaries) || writable(ctx, src)) return summaries
  // Again under the lock; if anything was written meanwhile, nothing is
  // written now and the next reading tries again.
  return src.update(async (state) => {
    if (overtaken(base, state)) return compute(ctx, state)
    const draft = structuredClone(state)
    let latest = await compute(ctx, draft)
    for (let pass = 0; pass < 3; pass++) {
      if (!(await settle(ctx, draft, latest))) break
      latest = await compute(ctx, draft)
    }
    // Checked again after the runs it took: otherwise the state stays as it
    // was and the next reading tries again.
    if (!writable(ctx, src)) state.lanes = draft.lanes
    return latest
  })
}

export function resolveLane(config: Config, name: string): Lane {
  const lane = config.lanes.find(
    (l) =>
      l.provider === name || l.label.toLowerCase() === name.toLowerCase(),
  )
  if (!lane)
    throw new Error(
      `unknown lane "${name}"; one of ${config.lanes.map((l) => l.label).join(", ")}`,
    )
  return lane
}

// A balance read now: in the Console (console), or an empty balance a request
// reported (empty). Read again if the reading crossed midnight or another
// writer re-based the lanes meanwhile.
export async function recordCheckpoint(
  provider: string,
  balance: number,
  source: "console" | "empty",
  config = loadConfig(),
  src: Sources = sources(config),
): Promise<void> {
  resolveLane(config, provider)
  let why = ""
  for (let attempt = 0; attempt < 3; attempt++) {
    const base = src.load()
    const ctx = await context(src.clock(), config, src)
    // Fetched outside the lock: the locked step only computes.
    await compute(ctx, base)
    await ctx.stats(1)
    why = writable(ctx, src) ?? ""
    if (why.startsWith("Hermes")) break
    if (why) continue
    const done = await src
      .update(async (state) => {
        if (overtaken(base, state)) {
          why = "another checkpoint was written meanwhile"
          return false
        }
        const summaries = await compute(ctx, state)
        why = writable(ctx, src) ?? ""
        if (why) return false
        await rebase(ctx, state, summaries, { provider, balance, source })
        return true
      })
      .catch((error: unknown) => {
        why = error instanceof Error ? error.message : String(error)
        return false
      })
    if (done) return
  }
  throw new Error(`checkpoint not recorded: ${why}`)
}

// A grant listed in the Console. It replaces any grant expiring the same day;
// an amount of 0 only removes.
export async function recordGrant(
  provider: string,
  amount: number,
  expires: string,
  granted: string,
  config = loadConfig(),
  src: Sources = sources(config),
): Promise<void> {
  resolveLane(config, provider)
  await src.update((state) => {
    const ls = (state.lanes[provider] ??= { grants: [] })
    ls.grants = ls.grants.filter(
      (g) => ymd(when(g.expires)) !== ymd(when(expires)),
    )
    if (amount > 0)
      ls.grants.push({ amount, granted, expires, source: "console" })
  })
}
