#!/usr/bin/env python3
"""Scoped Web acquisition through agent-browser, not a general browser/eval API.

The wrapper enforces its command surface. Terminal access and arbitrary website
side effects are NOT sandboxed. Only approved, sanitized demo sites qualify.
"""

import argparse
import fcntl
import json
import os
import re
import signal
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from approval import approved
from footage import media_path, probe, sha256
from tour import load, local, number, require, text, write


def origin(url):
    text(url, "target URL", 2000)
    u = urlsplit(url)
    require(u.scheme in ("http", "https") and u.hostname and not u.username and not u.password
            and not u.fragment, "http(s) target without credentials/fragment required")
    return f"{u.scheme}://{u.netloc}"


def scope_model(data):
    require(isinstance(data.get("form"), dict) and data["form"].get("screen_mode") == "capture", "only capture forms can acquire a session")
    from authored import form_model
    require(form_model(data["form"]) == data["form"], "capture proposal needs a fully defaulted valid form")
    require("acquisition_sha256" not in data, "editing approval reuses existing footage, never authorizes another capture")
    scope = data.get("scope")
    require(isinstance(scope, dict) and set(scope) == {
        "platform", "target", "origins", "start_state", "allowed_actions", "demo_data",
        "forbidden", "privacy", "max_seconds", "max_attempts", "max_actions", "read_only_recon"}, "invalid capture scope")
    require(scope["platform"] == "web", "macOS unavailable: recorder is main-display-only; cross-profile desktop guard unproven")
    require(scope["target"] == data["form"].get("target") and scope["start_state"] == data["form"].get("start_state"), "scope/form mismatch")
    require(isinstance(scope["origins"], list) and 1 <= len(scope["origins"]) <= 5, "1..5 exact origins required")
    require(all(origin(u) == u for u in scope["origins"]) and origin(scope["target"]) in scope["origins"], "target outside approved origins")
    require(scope["privacy"] == "sanitized-demo-only", "privacy masking/authenticated capture unavailable; supply sanitized input")
    require(scope["read_only_recon"] is True, "explicit reconnaissance consent required")
    text(scope["start_state"], "start state", 2000)
    require(isinstance(scope["forbidden"], list) and all(k in scope["forbidden"] for k in
            ("credentials", "purchases", "send", "delete", "uploads", "private-regions")), "required forbidden actions missing")
    require(isinstance(scope["demo_data"], list) and len(scope["demo_data"]) <= 20, "bounded dummy values required")
    for value in scope["demo_data"]:
        text(value, "dummy value", 100)
    actions = scope["allowed_actions"]
    require(isinstance(actions, dict) and set(actions) <= {"click", "type", "scroll"}, "unsupported allowed action")
    for op, selectors in actions.items():
        require(isinstance(selectors, list) and 0 < len(selectors) <= 30, "bounded approved selectors required")
        for selector in selectors:
            if op == "scroll":
                require(selector in ("up", "down"), "vertical scroll only")
            else:
                # No stale @refs, selector scripts, implicit Enter or secret inputs.
                require(isinstance(selector, str) and re.fullmatch(r"#[a-zA-Z][a-zA-Z0-9_-]{0,63}", selector), "exact approved DOM id required")
    number(scope["max_seconds"], 5, 180, "capture wall time")
    for key, high in (("max_attempts", 2), ("max_actions", 50)):
        require(type(scope[key]) is int and 1 <= scope[key] <= high, "invalid " + key)
    return scope


def commands_model(commands, scope):
    require(isinstance(commands, list) and len(commands) <= scope["max_actions"], "action budget exceeded")
    for cmd in commands:
        require(isinstance(cmd, list) and cmd and all(isinstance(v, str) for v in cmd), "command must be string argv")
        op = cmd[0]
        if op == "wait":
            require(len(cmd) == 2 and cmd[1].isdigit() and 0 <= int(cmd[1]) <= 5000, "wait limit 5 seconds")
        elif op in ("click", "type", "scroll"):
            require(len(cmd) == (2 if op == "click" else 3), "invalid command arity")
            require(cmd[1] in scope["allowed_actions"].get(op, []), "action/target not approved")
            if op == "type":
                require(cmd[2] in scope["demo_data"], "only exact approved dummy values may be typed")
            if op == "scroll":
                require(cmd[2].isdigit() and 1 <= int(cmd[2]) <= 1200, "scroll bounds 1..1200")
        else:
            require(False, "unsupported command; no eval, login, navigation, upload or shell")
    return commands


class Browser:
    def __init__(self, run, scope, session):
        self.run, self.scope = run, scope
        self.deadline = time.monotonic() + scope["max_seconds"]
        write(run / "browser.json", {"headed": False, "restoreSave": "never"})
        domains = sorted({urlsplit(u).hostname for u in scope["origins"]})
        self.argv = ["agent-browser", "--config", str(run / "browser.json"),
                     "--namespace", session, "--session", session, "--json",
                     "--allowed-domains", ",".join(domains)]
        # Never inherit shared profile/CDP, auth, plugin, proxy or init-script settings.
        self.env = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR", "LANG") if k in os.environ}
        self.env.update({"DO_NOT_TRACK": "1", "AGENT_BROWSER_IDLE_TIMEOUT_MS": "20000"})

    def call(self, *args, cleanup=False):
        remaining = self.deadline - time.monotonic()
        require(cleanup or remaining > 0, "capture lease expired")
        proc = subprocess.run(self.argv + list(args), cwd=self.run, env=self.env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=20 if cleanup else min(20, remaining))
        if proc.returncode:
            error = proc.stderr + proc.stdout
            for value in self.scope["demo_data"]:
                error = error.replace(value, "[approved dummy value]")
            write(self.run / ("error-" + uuid.uuid4().hex + ".json"), {"command": args[0], "stderr": error[:8000]})
        require(proc.returncode == 0, "browser command failed; inspect private evidence, do not blindly retry")
        result = json.loads(proc.stdout)
        require(result.get("success") is True, "browser rejected command")
        return result.get("data")

    def state(self):
        url = self.call("get", "url")["url"]
        require(origin(url) in self.scope["origins"], "redirect/navigation left approved origin")
        tabs = self.call("tab", "list")["tabs"]
        if len(tabs) != 1 or tabs[0].get("url") != url:
            write(self.run / ("tab-drift-" + uuid.uuid4().hex + ".json"), {"tabs": tabs, "url": url})
        require(len(tabs) == 1 and tabs[0].get("url") == url, "popup or tab drift; stop acquisition")
        return self.call("snapshot", "-i")


def acquire(job_value, proposal, approval_sha256, commands, recon=False, recover=False):
    data = approved(proposal, approval_sha256)
    scope = scope_model(data)
    commands = commands_model(commands, scope)
    require(not recon or not commands, "reconnaissance cannot perform actions")
    job = Path(job_value)
    require(job.is_absolute() and job.is_dir() and ".." not in job.parts
            and not any(p.is_symlink() for p in (job, *job.parents)), "existing physical job directory required")
    require(data["form"].get("source") == str(job / "source.json"), "capture session must bind the proposal's job/source path")
    lock_path = job / "capture.lock"
    require(not lock_path.is_symlink(), "symlink lease forbidden")
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("capture job already leased") from None
        runs = sorted(job.glob("take-*/lease.json"))
        require(not any(p.is_symlink() or p.parent.is_symlink() for p in runs), "symlink lease forbidden")
        unfinished = [p for p in runs if not (p.parent / "closed.json").exists()]
        if recover:
            require(unfinished, "no interrupted lease to recover")
            for path in unfinished:
                lease = load(path)
                require(lease["approval_sha256"] == approval_sha256, "recover with the original proposal approval")
                browser = Browser.__new__(Browser)
                browser.run, browser.scope = path.parent, scope
                browser.deadline = time.monotonic() + 40
                session = lease["session"]
                require(re.fullmatch(r"tour-[a-f0-9]{16}", session), "invalid owned session")
                browser.argv = ["agent-browser", "--config", str(path.parent / "browser.json"), "--namespace", session, "--session", session, "--json"]
                browser.env = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR", "LANG") if k in os.environ}
                browser.call("close", cleanup=True)
                write(path.parent / "closed.json", {"status": "interrupted", "pending_actions": "unknown; reconcile before a new proposal"})
            return {"status": "recovered", "retry": "new approval required; old actions remain unknown"}
        require(not unfinished, "interrupted lease: recover owned session first, never replay pending actions")
        failed = [p for p in runs if load(p.parent / "closed.json").get("status") != "complete"]
        require(not any(load(p)["approval_sha256"] == approval_sha256 for p in failed), "failed/interrupted approval cannot be replayed; reconcile and propose a new version")
        takes = [p for p in runs if not load(p).get("recon")]
        recons = [p for p in runs if load(p).get("recon")]
        require(recon or any(load(p)["approval_sha256"] == approval_sha256
                            for p in recons), "complete approved reconnaissance before recording")
        require(recon or len(takes) < scope["max_attempts"], "job attempt ceiling reached (failures count)")
        require(not recon or len(recons) < 4, "job reconnaissance ceiling reached (failures count)")
        run = job / ("take-" + uuid.uuid4().hex)
        run.mkdir(mode=0o700)
        session = "tour-" + uuid.uuid4().hex[:16]
        write(run / "lease.json", {"job": str(job), "approval_sha256": approval_sha256, "session": session, "recon": recon})
        browser = Browser(run, scope, session)
        started = False
        browser_closed = False
        status = "interrupted"
        old_handler = signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        try:
            browser.call("open", scope["target"])
            browser.call("set", "viewport", "1280", "720")
            snapshot = browser.state()
            write(run / "recon.json", snapshot)
            if recon:
                targets = {}
                for ref, description in list(snapshot.get("refs", {}).items())[:30]:
                    if re.fullmatch(r"e[0-9]+", ref):
                        targets[ref] = {"description": description,
                                        "id": browser.call("get", "attr", "@" + ref, "id")}
                write(run / "targets.json", targets)
                status = "complete"
                return {"recon": str(run), "recorded": False}
            # record start replaces the context: validate the new page and reacquire
            # its snapshot before any approved stateful action, never reuse @refs.
            started = True  # a timed-out start may already have begun recording
            before = browser.call("get", "text", "body")
            previous_tab = browser.call("tab", "list")["tabs"][0]["tabId"]
            approved(proposal, approval_sha256)
            browser.call("record", "start", str(run / "raw.webm"), scope["target"])
            tabs = browser.call("tab", "list")["tabs"]
            if len(tabs) == 2:
                old = [t for t in tabs if t["tabId"] == previous_tab and not t["active"]]
                new = [t for t in tabs if t["tabId"] != previous_tab and t["active"]]
                require(len(old) == len(new) == 1 and all(t["url"] == scope["target"] for t in tabs),
                        "unexpected tab during recording context replacement")
                browser.call("tab", "close", previous_tab)
            write(run / "recording-state.json", browser.state())
            require(browser.call("get", "text", "body") == before, "fresh recording context changed page state; stop and re-plan")
            with (run / "actions.jsonl").open("x") as journal:
                for index, cmd in enumerate(commands):
                    approved(proposal, approval_sha256)
                    browser.state()
                    if cmd[0] == "type":
                        kind = browser.call("get", "attr", cmd[1], "type").get("value")
                        require(kind in (None, "text", "search"), "secret/non-text field rejected before typing")
                    safe = cmd[:2] + (["[approved dummy value]"] if cmd[0] == "type" else cmd[2:])
                    def event(state):
                        journal.write(json.dumps({"index": index, "command": safe, "state": state,
                                                  "monotonic": time.monotonic()}) + "\n")
                        journal.flush()
                        os.fsync(journal.fileno())
                    event("pending")
                    browser.call(*cmd)
                    browser.state()
                    event("complete")
            approved(proposal, approval_sha256)
            browser.state()
            browser.call("record", "stop", cleanup=True)
            started = False
            browser.call("close", cleanup=True)
            browser_closed = True
            raw = media_path(str(run / "raw.webm"))
            info = probe(raw, decode=True)
            write(run / "receipt.json", {"job": str(job), "approval_sha256": approval_sha256,
                  "raw": str(raw), "sha256": sha256(raw), "probe": info, "status": "complete"})
            status = "complete"
            return {"capture": str(run), "receipt": str(run / "receipt.json"), "raw": str(raw)}
        finally:
            signal.signal(signal.SIGTERM, old_handler)
            try:
                if started:
                    try:
                        browser.call("record", "stop", cleanup=True)
                    except Exception:
                        status = "interrupted"
                if not browser_closed:
                    browser.call("close", cleanup=True)
            except Exception as exc:
                # No closed marker: recovery must reconcile this still-owned lease.
                raise ValueError("owned capture session cleanup failed; recover lease before continuing") from exc
            else:
                write(run / "closed.json", {"status": status})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--approval-sha256", required=True)
    parser.add_argument("--commands")
    parser.add_argument("--recon", action="store_true")
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    commands = load(local(args.commands, {".json"})) if args.commands else []
    print(json.dumps(acquire(args.job, args.proposal, args.approval_sha256, commands, args.recon, args.recover)))
