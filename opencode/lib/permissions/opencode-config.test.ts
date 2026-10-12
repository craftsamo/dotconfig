import { describe, expect, test } from "bun:test"
import { join } from "path"

// Characterization of the global shell rules in opencode.jsonc under OpenCode
// V2's matching: each simple command is checked as written, `*` crosses spaces
// and `/`, a trailing ` *` is optional, and the last matching rule wins.

type Rule = { action: string; resource: string; effect: "allow" | "ask" | "deny" }

const config = Bun.JSONC.parse(await Bun.file(join(import.meta.dir, "../../opencode.jsonc")).text()) as {
  permissions: Rule[]
  agents: Record<string, { permissions?: Rule[] }>
}
// What the built-in build agent resolves before the global rules.
const builtIn: Rule[] = [
  { action: "*", resource: "*", effect: "allow" },
  { action: "shell", resource: "*", effect: "ask" },
]
const rules = [...builtIn, ...config.permissions]

function matches(pattern: string, value: string, shell: boolean): boolean {
  const optional = shell && pattern.endsWith(" *")
  const body = optional ? pattern.slice(0, -2) : pattern
  const regex = body
    .split("")
    .map((c) => (c === "*" ? ".*" : c === "?" ? "." : c.replace(/[.+^${}()|[\]\\]/g, "\\$&")))
    .join("")
  return new RegExp(`^${regex}${optional ? "( .*)?" : ""}$`, "s").test(value)
}

const shell = (command: string) => {
  let effect = "ask"
  for (const r of rules) if (matches(r.action, "shell", false) && matches(r.resource, command, true)) effect = r.effect
  return effect
}

describe("global shell rules", () => {
  test("options before git's subcommand do not skip the asks", () => {
    for (const command of [
      "git --no-pager push --force origin x",
      "git -C x push origin topic",
      "git -P commit -m x",
      "git -c core.hooksPath=/dev/null commit -m x",
      "git --work-tree=. checkout other",
      "git -C . reset --hard",
      "git --no-pager config user.name x",
    ])
      expect([command, shell(command)]).toEqual([command, "ask"])
  })

  test("prefixes, wrappers and tabs match no allow", () => {
    for (const command of ["FOO=1 git push origin x", "env X=1 git push", "sh -c 'git push --force'", "git\tpush --force"])
      expect([command, shell(command)]).toEqual([command, "ask"])
  })

  test("remotes, aliases, extensions and gh flags before the verb ask", () => {
    for (const command of [
      "git remote set-url origin https://example.com/x",
      "git remote add other x",
      "git -C . remote rename origin x",
      "gh alias set --shell x 'git push -f'",
      "gh alias import aliases.yml",
      "gh extension exec stack push",
      "gh ext install x/y",
      "gh pr -R o/r merge 3",
      "gh pr -Ro/r merge 3",
      "gh pr checkout 3",
    ])
      expect([command, shell(command)]).toEqual([command, "ask"])
  })

  test("gh stack asks for everything but viewing", () => {
    for (const command of [
      "gh stack push",
      "gh stack submit --auto --open",
      "gh stack rebase",
      "gh stack sync",
      "gh stack link 3 4",
      "gh stack merge",
      "gh stack unstack",
      "gh stack -R o/r push",
      "gh stack init feat",
    ])
      expect([command, shell(command)]).toEqual([command, "ask"])
    for (const command of ["gh stack view", "gh stack view --json"]) expect([command, shell(command)]).toEqual([command, "allow"])
  })

  test("PR metadata from the shell asks; titles and bodies stay free", () => {
    for (const command of [
      "gh pr edit 3 --add-label bug",
      "gh pr edit 3 --remove-assignee x",
      "gh pr edit 3 --add-reviewer alice",
      "gh pr edit 3 --milestone v1",
      "gh pr edit 3 -m v1",
      "gh pr edit 3 --remove-milestone",
      'gh pr create --title "x" --body-file b.md --label bug',
      'gh pr create --title "x" --body-file b.md -r alice',
      'gh pr create --title "x" --body-file b.md -a @me',
      "gh pr -R o/r edit 3 --add-reviewer alice",
      "gh pr --repo o/r edit 3 --add-label bug",
      "gh pr create -r alice --title x --body-file b.md",
      "gh pr edit -m v1",
      "gh pr edit 3 -mv1",
      "gh pr -R o/r create -l bug --title x",
      "gh pr create -dr alice --title x --body-file b.md",
      "gh pr create -fa @me",
    ])
      expect([command, shell(command)]).toEqual([command, "ask"])
    for (const command of ['gh pr edit 3 --title "Fix label parsing"', "gh pr edit 3 --body-file b.md", 'gh pr create --title "Add milestone view" --body-file b.md'])
      expect([command, shell(command)]).toEqual([command, "allow"])
  })

  test("reads stay free", () => {
    for (const command of [
      "git status",
      "git log --oneline -5",
      "git --no-pager log -1",
      "git -C x diff",
      "git remote -v",
      "git remote get-url origin",
      "gh pr view 3 --json mergeable,mergeStateStatus",
      'gh pr create --title "Fix merge order" --body-file body.md',
      'gh pr comment 3 --body "checkout works again"',
      "gh alias list",
      "gh extension list",
      "lsof -nP -iTCP:3000 -sTCP:LISTEN",
    ])
      expect([command, shell(command)]).toEqual([command, "allow"])
  })
})

describe("global skill rules", () => {
  // OpenCode asks for a skill by its id, the directory holding SKILL.md, never
  // by the frontmatter `name`.
  const skill = (id: string) => {
    let effect = "ask"
    for (const r of rules) if (matches(r.action, "skill", false) && matches(r.resource, id, false)) effect = r.effect
    return effect
  }
  const skillsDir = join(import.meta.dir, "../../skills")
  const ids = (family: string) =>
    [...new Bun.Glob(`${family}/*/SKILL.md`).scanSync(skillsDir)].map((path) => path.split("/").at(-2)!)

  test("each git and approach skill is allowed by its id", () => {
    const allowed = [...ids("git"), ...ids("approach")]
    expect(allowed).toContain("commit")
    for (const id of allowed) expect([id, skill(id)]).toEqual([id, "allow"])
  })

  test("an unlisted skill still asks", () => {
    expect(skill("some-new-skill")).toBe("ask")
  })
})

describe("agent rules over a project's catch-all", () => {
  // OpenCode evaluates top-level rules (global, then project) before every
  // agent's own rules, so a project ending in `skill *: ask` re-asks what the
  // global top level allows unless the agent restates it.
  const full = config
  const project: Rule[] = [
    { action: "shell", resource: "*", effect: "ask" },
    { action: "skill", resource: "*", effect: "ask" },
  ]
  const decide = (agent: string, action: string, resource: string) => {
    let effect = "ask"
    for (const r of [...rules, ...project, ...(full.agents[agent]?.permissions ?? [])])
      if (matches(r.action, action, false) && matches(r.resource, resource, action === "shell")) effect = r.effect
    return effect
  }
  const topSkillAllows = full.permissions
    .filter((r) => r.action === "skill" && r.effect === "allow")
    .map((r) => r.resource)

  for (const agent of ["build", "plan"]) {
    test(`${agent} restates every global skill allow and lsof`, () => {
      const own = (full.agents[agent].permissions ?? [])
        .filter((r) => r.action === "skill" && r.effect === "allow")
        .map((r) => r.resource)
      expect(own.sort()).toEqual([...topSkillAllows].sort())
      for (const id of ["commit", "pullrequest", "new-feature", "japanese-writing"])
        expect([id, decide(agent, "skill", id)]).toEqual([id, "allow"])
      expect(decide(agent, "shell", "lsof -nP -iTCP:3000 -sTCP:LISTEN")).toBe("allow")
      expect(decide(agent, "skill", "some-new-skill")).toBe("ask")
      expect(decide(agent, "shell", "rm -rf build")).toBe("ask")
    })
  }

  test("build runs the project's scripts and installed tools, never a deployment unasked", () => {
    for (const command of ["nps lint", "nps test.web.e2e.worker", "pnpm run build", "pnpm test", "pnpm exec prettier --check src", "npm run lint"])
      expect([command, decide("build", "shell", command)]).toEqual([command, "allow"])
    for (const command of [
      "nps deploy.web",
      "pnpm exec wrangler deploy",
      "pnpm run deploy",
      "pnpm exec wrangler d1 execute DB --remote --command x",
      "pnpm exec wrangler secret put TOKEN",
      "pnpm run publish:docs",
      "pnpm exec vercel --prod",
      "pnpm dlx create-x",
      "npx nps lint",
      "FOO=1 nps lint",
    ])
      expect([command, decide("build", "shell", command)]).toEqual([command, "ask"])
    expect(decide("plan", "shell", "nps lint")).toBe("ask")
  })
})

describe("subagents that reset shell to ask", () => {
  // worker, debugger and verifier start their shell rules with `*: ask`, which
  // takes back the top-level read allows; they restate the plain reads.
  const front = async (name: string) => {
    const text = await Bun.file(join(import.meta.dir, `../../agents/${name}.md`)).text()
    return Bun.YAML.parse(text.split("---")[1]) as { permissions: Rule[] }
  }
  for (const name of ["worker", "debugger", "verifier"]) {
    test(`${name} reads through the shell without asking`, async () => {
      const own = (await front(name)).permissions
      const decide = (command: string) => {
        let effect = "ask"
        for (const r of [...rules, ...own]) if (matches(r.action, "shell", false) && matches(r.resource, command, true)) effect = r.effect
        return effect
      }
      for (const command of ["cat playwright.config.ts playwright.worker.config.ts", "grep -n share src/index.ts", "head -30 a.ts", "ls packages", "rg -n token src", "ps -axo pid,command"])
        expect([command, decide(command)]).toEqual([command, "allow"])
      for (const command of ["node -e 'x'", "kill -TERM 1", "awk '{print}' a"]) expect([command, decide(command)]).toEqual([command, "ask"])
      if (name === "debugger") expect(decide("cat a > b")).toBe("ask")
    })
  }
})
