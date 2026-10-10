import { describe, expect, test } from "bun:test"
import { chmodSync, existsSync, mkdtempSync, rmSync, writeFileSync } from "fs"
import { tmpdir } from "os"
import { join } from "path"
import { exec, run, withTempFile } from "./exec"

describe("exec", () => {
  test("captures stdout, stderr and the exit code, and feeds stdin", async () => {
    expect(await exec(["sh", "-c", "cat; echo err >&2; exit 3"], { stdin: "in" })).toEqual({
      ok: false,
      code: 3,
      stdout: "in",
      stderr: "err\n",
    })
  })

  test("looks programs up on the PATH it is given", async () => {
    const bin = mkdtempSync(join(tmpdir(), "exec-bin-"))
    try {
      writeFileSync(join(bin, "fake-tool"), "#!/bin/sh\necho fake \"$@\"\n")
      chmodSync(join(bin, "fake-tool"), 0o755)
      const out = await run(["fake-tool", "a"], { env: { ...process.env, PATH: `${bin}:${process.env.PATH}` } })
      expect(out).toBe("fake a\n")
    } finally {
      rmSync(bin, { recursive: true, force: true })
    }
  })

  test("run throws with the command line and stderr, falling back to stdout", async () => {
    await expect(run(["sh", "-c", "echo bad >&2; exit 2"])).rejects.toThrow("sh -c echo bad >&2; exit 2 failed (exit 2):\nbad")
    await expect(run(["sh", "-c", "echo only-out; exit 1"])).rejects.toThrow(/\nonly-out$/)
  })
})

describe("withTempFile", () => {
  test("removes the file afterwards, also when the callback throws", async () => {
    let kept = ""
    await expect(
      withTempFile("exec-test", ".txt", "body", async (path) => {
        kept = path
        expect(await Bun.file(path).text()).toBe("body")
        throw new Error("boom")
      }),
    ).rejects.toThrow("boom")
    expect(kept.endsWith(".txt")).toBe(true)
    expect(existsSync(kept)).toBe(false)
  })
})
