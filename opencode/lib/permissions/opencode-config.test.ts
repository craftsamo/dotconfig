import { describe, expect, test } from "bun:test"
import { join } from "path"

// Characterization of the global shell rules in opencode.jsonc under OpenCode
// V2's matching: each simple command is checked as written, `*` crosses spaces
// and `/`, a trailing ` *` is optional, and the last matching rule wins.

type Rule = { action: string; resource: string; effect: "allow" | "ask" | "deny" }

const config = Bun.JSONC.parse(await Bun.file(join(import.meta.dir, "../../opencode.jsonc")).text()) as {
  permissions: Rule[]
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
    ])
      expect([command, shell(command)]).toEqual([command, "allow"])
  })
})
