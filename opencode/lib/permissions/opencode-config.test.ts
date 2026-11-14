import { describe, expect, test } from "bun:test"
import { join } from "path"

// Characterization of the global shell rules in opencode.jsonc under OpenCode
// V2's matching: each simple command is checked as written, `*` crosses spaces
// and `/`, a trailing ` *` is optional, and the last matching rule wins.

type Rule = { action: string; resource: string; effect: "allow" | "ask" | "deny" }

const config = Bun.JSONC.parse(await Bun.file(join(import.meta.dir, "../../opencode.jsonc")).text()) as {
  permissions: Rule[]
  agents: Record<string, { permissions?: Rule[] }>
  plugins: (string | { package: string; options?: { worktree_root?: string } })[]
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

describe("policies", () => {
  // OpenCode skips a statement whose action it does not recognize, with only a
  // log warning; 2.0.25 renamed `permission` to `tool.use` that way.
  const policies = (config as unknown as { policies: Rule[]; experimental?: { policies?: unknown } }).policies

  test("every statement is a top-level tool.use deny on <action>:<resource>", () => {
    expect((config as { experimental?: { policies?: unknown } }).experimental?.policies).toBeUndefined()
    expect(policies.length).toBeGreaterThan(0)
    for (const p of policies) {
      expect([p.resource, p.action, p.effect]).toEqual([p.resource, "tool.use", "deny"])
      expect(p.resource).toMatch(/^[a-z_]+:./)
    }
  })

  test("each shell policy keeps a matching permission deny", () => {
    for (const p of policies.filter((p) => p.resource.startsWith("shell:"))) {
      const command = p.resource.slice("shell:".length).replaceAll("*", "x")
      expect([command, shell(command)]).toEqual([command, "deny"])
    }
  })
})

describe("Git tools", () => {
  const decide = (action: string) => {
    let effect = "ask"
    for (const r of rules) if (matches(r.action, action, false) && matches(r.resource, "*", false)) effect = r.effect
    return effect
  }

  test("git-tools supplies the worktree strategy under ~/Worktrees", () => {
    const plugin = config.plugins.find((plugin) => typeof plugin !== "string" && plugin.package.startsWith("@craftsamo/git-tools@"))
    expect(plugin).toBeDefined()
    expect(typeof plugin === "object" && plugin.options?.worktree_root).toBe("~/Worktrees")
  })

  test("local writes are allowed, arbitrary commands and pushes ask", () => {
    for (const tool of ["git_commit_stage", "git_commit_create", "git_commit_amend", "git_rebase_start", "git_rebase_resume", "git_rebase_split", "git_worktree_add", "git_worktree_remove"])
      expect([tool, decide(tool)]).toEqual([tool, "allow"])
    for (const tool of ["git_push_send", "git_commit_verify", "git_future_write"])
      expect([tool, decide(tool)]).toEqual([tool, "ask"])
    for (const tool of ["opencode_worktree_create", "opencode_worktree_remove"])
      expect(rules.some((rule) => rule.action === tool)).toBe(false)
  })
})

describe("global outside-directory rules", () => {
  // The built-in rules allow every action since 2.0.25, outside directories
  // included; the global ask restores the prompt. Resources are the directory
  // with `/*` appended.
  const outside = (resource: string, own: Rule[] = []) => {
    let effect = "ask"
    for (const r of [...rules, ...own])
      if (matches(r.action, "external_directory", false) && matches(r.resource, resource, false)) effect = r.effect
    return effect
  }
  const home = process.env.HOME ?? "/Users/x"

  test("a directory outside the Location asks", () => {
    for (const resource of ["/etc/*", `${home}/Documents/*`, `${home}/ghq/github.com/o/other/*`, "/tmp/*"])
      expect([resource, outside(resource)]).toEqual([resource, "ask"])
  })

  test("Plan reads the source checkouts without a prompt; Build and credentials still ask", () => {
    const plan = config.agents.plan.permissions ?? []
    const build = config.agents.build.permissions ?? []
    for (const resource of ["~/ghq/github.com/o/other/*", "~/ghq/github.com/o/other/src/*", "~/Worktrees/repo/topic/*"]) {
      expect([resource, outside(resource, plan)]).toEqual([resource, "allow"])
      expect([resource, outside(resource, build)]).toEqual([resource, "ask"])
    }
    for (const resource of ["~/ghqx/*", "~/.aws/*", "~/.config/gh/*", "~/.local/share/opencode/*"])
      expect([resource, outside(resource, plan)]).toEqual([resource, "ask"])
  })

  test("skill directories and OpenCode's scratch directory stay open", () => {
    for (const resource of [
      "~/.agents/skills/commit/references/*",
      "~/.config/opencode/skills/approach/new-feature/*",
      "/private/var/folders/xy/abc123/T/opencode/*",
      "/private/var/folders/xy/abc123/T/opencode/oc-diff/v2.1.2/*",
    ])
      expect([resource, outside(resource)]).toEqual([resource, "allow"])
    expect(outside("/private/var/folders/xy/abc123/T/other/*")).toBe("ask")
  })

  test("read-only subagents that allow outside reads keep that allow", async () => {
    const text = await Bun.file(join(import.meta.dir, "../../agents/explore-medium.md")).text()
    const own = (Bun.YAML.parse(text.split("---")[1]) as { permissions: Rule[] }).permissions
    expect(outside("/etc/*", own)).toBe("allow")
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
      for (const id of ["commit", "pullrequest", "new-feature", "japanese-writing", "git-repo", "git-commit", "git-rebase", "git-worktree", "git-push"])
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

  test("a Signal write asks in build and is denied in plan, where reads stay open", () => {
    for (const tool of ["signal_message_send", "signal_file_send", "signal_message_delete"]) {
      expect([tool, decide("build", tool, "default/group:abc")]).toEqual([tool, "ask"])
      expect([tool, decide("plan", tool, "default/group:abc")]).toEqual([tool, "deny"])
    }
    expect(decide("plan", "signal_chat_read", "*")).toBe("allow")
    expect(decide("build", "skill", "signal-sends")).toBe("allow")
  })

  test("a Telegram write asks in build and is denied in plan, where reads stay open", () => {
    for (const tool of ["telegram_message_send", "telegram_file_send", "telegram_sync_add", "telegram_chat_mark_read", "telegram_grant_create"]) {
      expect([tool, decide("build", tool, "default/-100123")]).toEqual([tool, "ask"])
      expect([tool, decide("plan", tool, "default/-100123")]).toEqual([tool, "deny"])
    }
    expect(decide("plan", "telegram_chat_read", "*")).toBe("allow")
    expect(decide("build", "skill", "telegram-sends")).toBe("allow")
    expect(decide("plan", "skill", "telegram-chats")).toBe("allow")
  })

  test("read-only primaries read Telegram but never mark a chat read", async () => {
    for (const agent of ["design", "review", "debug"]) {
      const text = await Bun.file(join(import.meta.dir, `../../agents/${agent}.md`)).text()
      const own = (Bun.YAML.parse(text.split("---")[1]) as { permissions: Rule[] }).permissions
      const effect = (tool: string) => {
        let result = "ask"
        for (const r of own) if (matches(r.action, tool, false) && matches(r.resource, "default/-100123", false)) result = r.effect
        return result
      }
      for (const tool of ["telegram_account_read", "telegram_chat_read", "telegram_sync_read"])
        expect([agent, tool, effect(tool)]).toEqual([agent, tool, "allow"])
      for (const tool of ["telegram_chat_mark_read", "telegram_message_send", "telegram_sync_add"])
        expect([agent, tool, effect(tool)]).toEqual([agent, tool, "deny"])
    }
  })

  test("a Discord write asks in build and is denied in plan, where reads stay open", () => {
    for (const tool of [
      "discord_message_send",
      "discord_file_send",
      "discord_sync_add",
      "discord_read_mark",
      "discord_reaction_add",
      "discord_role_assign",
      "discord_export_create",
      "discord_grant_create",
    ]) {
      expect([tool, decide("build", tool, "default/1400000000000000401")]).toEqual([tool, "ask"])
      expect([tool, decide("plan", tool, "default/1400000000000000401")]).toEqual([tool, "deny"])
    }
    expect(decide("plan", "discord_chat_read", "*")).toBe("allow")
    expect(decide("plan", "discord_search_read", "*")).toBe("allow")
    expect(decide("build", "skill", "discord-sends")).toBe("allow")
    expect(decide("plan", "skill", "discord-chats")).toBe("allow")
  })

  test("read-only primaries read Discord but never mark a chat read", async () => {
    for (const agent of ["design", "review", "debug"]) {
      const text = await Bun.file(join(import.meta.dir, `../../agents/${agent}.md`)).text()
      const own = (Bun.YAML.parse(text.split("---")[1]) as { permissions: Rule[] }).permissions
      const effect = (tool: string) => {
        let result = "ask"
        for (const r of own) if (matches(r.action, tool, false) && matches(r.resource, "default/1400000000000000401", false)) result = r.effect
        return result
      }
      for (const tool of [
        "discord_account_read",
        "discord_sync_read",
        "discord_chat_read",
        "discord_search_read",
        "discord_inbox_read",
        "discord_people_read",
        "discord_server_read",
        "discord_history_read",
        "discord_role_read",
      ])
        expect([agent, tool, effect(tool)]).toEqual([agent, tool, "allow"])
      for (const tool of ["discord_read_mark", "discord_message_send", "discord_sync_add", "discord_role_assign"])
        expect([agent, tool, effect(tool)]).toEqual([agent, tool, "deny"])
    }
  })

  test("a WhatsApp write asks in build and is denied in plan, where reads stay open", () => {
    for (const tool of [
      "whatsapp_message_send",
      "whatsapp_file_send",
      "whatsapp_file_save",
      "whatsapp_history_backfill",
      "whatsapp_chat_mark",
      "whatsapp_message_delete",
      "whatsapp_grant_create",
    ]) {
      expect([tool, decide("build", tool, "default/120363000000000000@g.us")]).toEqual([tool, "ask"])
      expect([tool, decide("plan", tool, "default/120363000000000000@g.us")]).toEqual([tool, "deny"])
    }
    expect(decide("plan", "whatsapp_chat_read", "*")).toBe("allow")
    expect(decide("plan", "whatsapp_contact_read", "*")).toBe("allow")
    expect(decide("build", "skill", "whatsapp-sends")).toBe("allow")
    expect(decide("plan", "skill", "whatsapp-chats")).toBe("allow")
  })

  test("read-only primaries read WhatsApp but never backfill or mark a chat read", async () => {
    for (const agent of ["design", "review", "debug"]) {
      const text = await Bun.file(join(import.meta.dir, `../../agents/${agent}.md`)).text()
      const own = (Bun.YAML.parse(text.split("---")[1]) as { permissions: Rule[] }).permissions
      const effect = (tool: string) => {
        let result = "ask"
        for (const r of own) if (matches(r.action, tool, false) && matches(r.resource, "default/120363000000000000@g.us", false)) result = r.effect
        return result
      }
      for (const tool of [
        "whatsapp_account_read",
        "whatsapp_chat_read",
        "whatsapp_contact_read",
        "whatsapp_grant_read",
      ])
        expect([agent, tool, effect(tool)]).toEqual([agent, tool, "allow"])
      for (const tool of ["whatsapp_history_backfill", "whatsapp_chat_mark", "whatsapp_message_send", "whatsapp_file_save"])
        expect([agent, tool, effect(tool)]).toEqual([agent, tool, "deny"])
    }
  })

  test("a GitHub write asks in build and is denied in plan, where reads stay open", () => {
    for (const tool of ["github_issue_create", "github_issue_edit", "github_pr_create", "github_pr_merge", "github_project_item_edit"]) {
      expect([tool, decide("build", tool, "owner/repo")]).toEqual([tool, "ask"])
      expect([tool, decide("plan", tool, "owner/repo")]).toEqual([tool, "deny"])
    }
    expect(decide("plan", "github_issue_read", "*")).toBe("allow")
    expect(decide("plan", "github_pr_read", "*")).toBe("allow")
    expect(decide("build", "skill", "github-issues")).toBe("allow")
  })

  test("a Cloudflare write asks in build and is denied in plan, where reads stay open", () => {
    for (const tool of [
      "cloudflare_dns_record_add",
      "cloudflare_dns_record_edit",
      "cloudflare_dns_record_delete",
      "cloudflare_zone_setting_edit",
      "cloudflare_zone_setting_weaken",
      "cloudflare_zone_cache_purge",
      "cloudflare_zone_cache_purge_all",
      "cloudflare_workers_rollback",
      "cloudflare_pages_rollback",
      "cloudflare_tunnel_route_add",
      "cloudflare_storage_delete",
      "cloudflare_email_rule_add",
      "cloudflare_rules_edit",
      "cloudflare_grant_create",
    ]) {
      expect([tool, decide("build", tool, "example.com")]).toEqual([tool, "ask"])
      expect([tool, decide("plan", tool, "example.com")]).toEqual([tool, "deny"])
    }
    expect(decide("plan", "cloudflare_zone_read", "*")).toBe("allow")
    expect(decide("plan", "cloudflare_dns_read", "*")).toBe("allow")
    expect(decide("build", "skill", "cloudflare-dns")).toBe("allow")
    expect(decide("plan", "skill", "cloudflare-dns")).toBe("allow")
  })

  test("read-only primaries read Cloudflare but never change it", async () => {
    for (const agent of ["design", "review", "debug"]) {
      const text = await Bun.file(join(import.meta.dir, `../../agents/${agent}.md`)).text()
      const own = (Bun.YAML.parse(text.split("---")[1]) as { permissions: Rule[] }).permissions
      const effect = (tool: string) => {
        let result = "ask"
        for (const r of own) if (matches(r.action, tool, false) && matches(r.resource, "example.com", false)) result = r.effect
        return result
      }
      for (const tool of [
        "cloudflare_zone_read",
        "cloudflare_dns_read",
        "cloudflare_account_read",
        "cloudflare_rules_read",
        "cloudflare_grant_read",
      ])
        expect([agent, tool, effect(tool)]).toEqual([agent, tool, "allow"])
      for (const tool of [
        "cloudflare_dns_record_add",
        "cloudflare_dns_record_delete",
        "cloudflare_zone_setting_weaken",
        "cloudflare_zone_cache_purge_all",
        "cloudflare_rules_edit",
        "cloudflare_grant_create",
      ])
        expect([agent, tool, effect(tool)]).toEqual([agent, tool, "deny"])
    }
  })

  for (const agent of ["plan", "explore"]) {
    test(`${agent} denies Git writes and allows reads`, () => {
      for (const tool of ["git_commit_stage", "git_commit_create", "git_commit_amend", "git_commit_verify", "git_rebase_start", "git_rebase_resume", "git_rebase_split", "git_worktree_add", "git_worktree_remove", "git_push_send", "git_future_write"])
        expect([tool, decide(agent, tool, "*")]).toEqual([tool, "deny"])
      for (const tool of ["git_repo_read", "git_commit_read", "git_rebase_read", "git_worktree_read", "git_push_read"])
        expect([tool, decide(agent, tool, "*")]).toEqual([tool, "allow"])
    })
  }
})

describe("subagents that reset shell to ask", () => {
  // worker, worker-deep, refactorer, debugger and verifier start their shell
  // rules with `*: ask`, which takes back the top-level read allows; they
  // restate the plain reads.
  const front = async (name: string) => {
    const text = await Bun.file(join(import.meta.dir, `../../agents/${name}.md`)).text()
    return Bun.YAML.parse(text.split("---")[1]) as { permissions: Rule[] }
  }
  for (const name of ["worker", "worker-deep", "refactorer", "debugger", "verifier"]) {
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

  for (const name of ["review", "reviewer", "debugger"]) {
    test(`${name} reads GitHub through github-tools but cannot write`, async () => {
      const own = (await front(name)).permissions
      const decide = (action: string) => {
        let effect = "ask"
        for (const r of [...rules, ...own]) if (matches(r.action, action, false) && matches(r.resource, "*", false)) effect = r.effect
        return effect
      }
      expect(decide("github_issue_edit")).toBe("deny")
      expect(decide("github_pr_read")).toBe("allow")
    })
  }

  for (const name of ["debug", "review", "design", "explore-medium", "explore-high", "explore-max", "debugger", "reviewer", "reviewer-deep"]) {
    test(`${name} allows Git reads but denies pushes`, async () => {
      const own = (await front(name)).permissions
      const decide = (action: string) => {
        let effect = "ask"
        for (const r of [...rules, ...own]) if (matches(r.action, action, false) && matches(r.resource, "*", false)) effect = r.effect
        return effect
      }
      for (const tool of ["git_repo_read", "git_commit_read", "git_rebase_read", "git_worktree_read", "git_push_read"])
        expect([tool, decide(tool)]).toEqual([tool, "allow"])
      expect(decide("git_push_send")).toBe("deny")
    })
  }

  test("verifier asks before running a command at each commit", async () => {
    const own = (await front("verifier")).permissions
    expect(own).toContainEqual({ action: "git_commit_verify", resource: "*", effect: "ask" })
  })

  for (const name of ["worker", "worker-deep", "refactorer"]) {
    test(`${name} can access task worktrees under ~/Worktrees`, async () => {
      const own = (await front(name)).permissions
      expect(own).toContainEqual({ action: "external_directory", resource: "~/Worktrees/*", effect: "allow" })
    })
  }

  // Formatting belongs to the verifier; these agents run checks, and a check
  // that would write files or snapshots asks first.
  for (const name of ["refactorer", "worker", "worker-deep"]) {
    test(`${name} runs checks unasked, but asks before a check writes files`, async () => {
      const own = (await front(name)).permissions
      const decide = (command: string) => {
        let effect = "ask"
        for (const r of [...rules, ...own]) if (matches(r.action, "shell", false) && matches(r.resource, command, true)) effect = r.effect
        return effect
      }
      for (const command of [
        "npm test",
        "tsc --noEmit",
        "tsc --noEmit -p .",
        "tsc -p tsconfig.app.json --noEmit",
        "node_modules/.bin/tsc --noEmit -p .",
        "eslint src",
        "ruff check .",
        "git diff main...HEAD",
      ])
        expect([command, decide(command)]).toEqual([command, "allow"])
      if (name === "refactorer")
        for (const command of [
          "node --test test/orders.test.ts",
          "python3 -m unittest discover -s py/tests -t py",
          "python3 -m pytest tests -q",
          "uv run pytest -q",
          "stylelint 'web/**/*.css'",
        ])
          expect([command, decide(command)]).toEqual([command, "allow"])
      for (const command of [
        "nps format",
        "tsc",
        "tsc -b",
        "tsc --noEmitOnError",
        "eslint --fix src",
        "ruff check --fix .",
        "stylelint --fix x.css",
        "cargo clippy --fix",
        "prettier --check --write .",
        "vitest run -u",
        "jest --updateSnapshot",
        "node --test --test-update-snapshots",
        "python3 -m pytest --snapshot-update",
        "git diff --output=x.patch",
        "tsc --noEmit --incremental",
        "eslint --cache src",
        "python3 -m pytest --junitxml=report.xml",
        "cat a > b",
        "rg token src > hits.txt",
      ])
        expect([command, decide(command)]).toEqual([command, "ask"])
      expect(decide("git commit -m x")).toBe("deny")
    })
  }

  test("design reads the repository and writes only drafts", async () => {
    const own = (await front("design")).permissions
    const decide = (action: string, resource: string) => {
      let effect = "ask"
      for (const r of [...rules, ...own])
        if (matches(r.action, action, false) && matches(r.resource, resource, action === "shell")) effect = r.effect
      return effect
    }
    expect(decide("read", "src/app/page.tsx")).toBe("allow")
    expect(decide("read", "apps/web/.env")).toBe("deny")
    expect(decide("edit", "src/app/page.tsx")).toBe("deny")
    expect(decide("edit", "/w/Projects/Acme/.agent/20261012-form/design/index.html")).toBe("allow")
    expect(decide("edit", "/w/Projects/Acme/.agent/job/x.env")).toBe("deny")
    expect(decide("git_commit_create", "*")).toBe("deny")
    expect(decide("git_repo_read", "*")).toBe("allow")
    for (const command of ["git log --oneline -5", "git diff main", "ls apps"]) expect([command, decide("shell", command)]).toEqual([command, "allow"])
    for (const command of ["git diff --output=x.patch", "git log > x", "rm -rf src", "node -e 'x'"])
      expect([command, decide("shell", command)]).toEqual([command, "ask"])
  })
})
