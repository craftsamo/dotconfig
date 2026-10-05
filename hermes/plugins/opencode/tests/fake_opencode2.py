"""A stand-in for `opencode serve` (OpenCode 2): the API routes the runner uses.

Sessions persist in $ENGINEER_FAKE_STATE so a resume can land on a later
server, as with the real database. Each session's directory receives
invocation.json: the calls, the session as last stored, prompts and replies.

$ENGINEER_FAKE picks the turn: ok, question, error, none (idle without an
outcome), sleep (runs until interrupted, with a child process), ask (one
permission request on the session), ask-subagent (one on a child session,
listed only per location, as on 2.0.23), stale (the prompt starts no turn and
wait returns at once: only an earlier turn's outcome exists), bad-rules /
bad-model (the session keeps something other than what was set), no-rules (the
agent resolves without a ruleset), crash (the
server exits mid-turn). Agents resolve only after a few requests, as the real
server loads them shortly after it listens.
"""
import base64, http.server, json, os, pathlib, re, subprocess, sys, threading, time, urllib.parse

STATE = pathlib.Path(os.environ["ENGINEER_FAKE_STATE"])
AUTH = "Basic " + base64.b64encode(f"opencode:{os.environ['OPENCODE_PASSWORD']}".encode()).decode()
BEHAVIOR = os.environ.get("ENGINEER_FAKE", "ok")
PINS = {"hermes-plan": {"providerID": "anthropic", "id": "claude-opus-5-5", "variant": "high"},
        "hermes-build": {"providerID": "openai", "id": "gpt-6.1-sol", "variant": "medium"}}
GLOBAL_DENIES = [{"action": "shell", "resource": "sudo *", "effect": "deny"},
                 {"action": "shell", "resource": "secret get*", "effect": "deny"},
                 {"action": "external_directory", "resource": "/secrets/*", "effect": "deny"}]
LOCK = threading.RLock()
IDLE, RUNS = {}, {}
AGENT_CALLS = [0]


def load():
    return json.loads(STATE.read_text()) if STATE.exists() else {"sessions": {}, "count": 0}


def store(state):
    STATE.write_text(json.dumps(state))


def note(state, sid, **fields):
    session = state["sessions"][sid]
    path = pathlib.Path(session["location"]["directory"]) / "invocation.json"
    record = json.loads(path.read_text()) if path.exists() else {"calls": [], "prompts": [], "replies": []}
    lists = {"call": "calls", "prompt": "prompts", "reply": "replies"}
    for key, value in fields.items():
        if key in lists:
            record[lists[key]].append(value)
        else:
            record[key] = value
    record["session"] = {k: v for k, v in session.items() if k != "messages"}
    record["server_env_has_policy"] = any(k in os.environ for k in ("OPENCODE_CONFIG_CONTENT", "OPENCODE_PERMISSION"))
    path.write_text(json.dumps(record))


def now():
    return int(time.time() * 1000)


def add(sid, *messages, **fields):
    with LOCK:
        state = load()
        session = state["sessions"][sid]
        session.setdefault("messages", []).extend(messages)
        session.update(fields)
        store(state)


def ask(sid, owner):
    RUNS[sid]["pending"] = [{"id": "per_1", "sessionID": owner, "action": "shell",
                             "resources": ["git push origin topic"], "save": ["git push *"]}]
    while not RUNS[sid].get("reply") and not RUNS[sid].get("interrupted"):
        time.sleep(0.05)
    RUNS[sid]["pending"] = []
    return RUNS[sid].get("reply") or {}


def turn(sid):
    state = load()
    directory = pathlib.Path(state["sessions"][sid]["location"]["directory"])
    text, outcome, tools = "RESULT_OK", "succeeded", []
    if BEHAVIOR == "question":
        text = "ASK_CLIENT: choose A or B"
    elif BEHAVIOR == "error":
        text, outcome = "", "failed"
    elif BEHAVIOR == "none":
        outcome = None
    elif BEHAVIOR == "crash":
        time.sleep(0.3)
        os._exit(1)
    elif BEHAVIOR == "sleep":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(90)"])
        (directory / "child-pid").write_text(str(child.pid))
        while not RUNS[sid].get("interrupted"):
            time.sleep(0.05)
        child.kill()
        text, outcome = "", "interrupted"
    elif BEHAVIOR in ("ask", "ask-subagent"):
        owner = sid
        if BEHAVIOR == "ask-subagent":
            owner = "ses_child"
            with LOCK:
                state = load()
                state["sessions"][owner] = {"id": owner, "parentID": sid, "location": state["sessions"][sid]["location"]}
                store(state)
        reply = ask(sid, owner)
        if RUNS[sid].get("interrupted"):
            text, outcome = "", "interrupted"
        else:
            text = "PUSHED" if reply.get("decision") == "once" else "SKIPPED: " + str(reply.get("message"))
            if reply.get("decision") != "once":
                tools = [{"type": "tool", "name": "shell", "state": {"status": "error", "input": {
                    "command": "git push origin topic"}, "error": {"type": "permission.rejected"}}}]
    created = now()
    step = {"id": f"msg_a{created}", "type": "assistant", "time": {"created": created, "completed": created},
            "content": [*tools, *([{"type": "text", "text": text}] if text else [])]}
    idle = {"id": f"msg_i{created}", "type": "idle", "time": {"created": created},
            **({"outcome": outcome} if outcome else {})}
    add(sid, step, idle, diff_for=RUNS[sid]["user"],
        diff=[{"file": "a.txt", "status": "added", "additions": 1, "deletions": 0,
               "patch": "diff --git a/a.txt b/a.txt\n+x\n"}])
    IDLE[sid].set()


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, data=None, wrap=True):
        body = b"" if data is None else json.dumps({"data": data} if wrap else data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_any(self, method):
        if self.headers.get("Authorization") != AUTH:
            return self.reply(401, {})
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        path, _, query = self.path.partition("?")
        params = dict(urllib.parse.parse_qsl(query))
        if path == "/api/info":
            return self.reply(200, {"version": "2.0.23"}, wrap=False)
        match = re.fullmatch(r"/api/agent/([\w-]+)", path)
        if match:
            AGENT_CALLS[0] += 1
            if AGENT_CALLS[0] < 3 or match.group(1) not in PINS or "location[directory]" not in params:
                return self.reply(404, {})
            pin = None if os.environ.get("ENGINEER_FAKE_NO_PIN") else PINS[match.group(1)]
            ruleset = [{"action": "*", "resource": "*", "effect": "allow"}, *GLOBAL_DENIES]
            return self.reply(200, {"id": match.group(1), **({"model": pin} if pin else {}),
                                    **({} if BEHAVIOR == "no-rules" else {"permissions": ruleset})})
        if path == "/api/permission/request":
            if "location[directory]" not in params:
                return self.reply(400, {})
            pending = [r for run in RUNS.values() for r in run.get("pending", [])]
            return self.reply(200, pending)
        with LOCK:
            state = load()
            if path == "/api/session" and method == "POST":
                state["count"] += 1
                sid = f"ses_fake{state['count']}"
                state["sessions"][sid] = {"id": sid, "agent": body.get("agent"), "model": body.get("model"),
                                          "permissions": body.get("permissions"), "location": body["location"]}
                if BEHAVIOR == "bad-rules":
                    state["sessions"][sid]["permissions"] = body["permissions"][:-1]
                if BEHAVIOR == "bad-model":
                    state["sessions"][sid]["model"] = {"providerID": "openai", "id": "something-else"}
                store(state)
                note(state, sid, call=["POST", "/api/session"], created=body)
                return self.reply(200, {k: v for k, v in state["sessions"][sid].items() if k != "messages"})
            match = re.fullmatch(r"/api(?:/experimental)?/session/(ses_\w+)(?:/(\w+))?(?:/(per_\w+)/reply)?", path)
            if not match or match.group(1) not in state["sessions"]:
                return self.reply(404, {})
            sid, verb, pid = match.groups()
            session = state["sessions"][sid]
            note(state, sid, call=[method, verb or ""])
            if verb is None and method == "GET":
                return self.reply(200, {k: v for k, v in session.items() if k not in ("messages", "diff")})
            if verb is None and method == "PATCH":
                session["permissions"] = body["permissions"]
            elif verb == "agent":
                session["agent"] = body["agent"]
            elif verb == "model":
                session["model"] = body["model"]
            elif verb == "fork":
                fid = "ses_fork"
                state["sessions"][fid] = {**session, "id": fid, "messages": list(session.get("messages", []))}
                store(state)
                return self.reply(200, {k: v for k, v in state["sessions"][fid].items() if k != "messages"})
            elif verb == "prompt":
                created = now()
                user = {"id": f"msg_u{created}", "type": "user", "time": {"created": created}}
                note(state, sid, prompt=body["text"])
                if BEHAVIOR == "stale":
                    IDLE[sid] = threading.Event()
                    IDLE[sid].set()
                    return self.reply(200, user)
                session.setdefault("messages", []).append(user)
                store(state)
                RUNS[sid] = {"user": user["id"]}
                IDLE[sid] = threading.Event()
                threading.Thread(target=turn, args=(sid,), daemon=True).start()
                return self.reply(200, user)
            elif verb == "wait":
                event = IDLE.get(sid)
            if verb in (None, "agent", "model"):
                store(state)
                return self.reply(200, {k: v for k, v in session.items() if k not in ("messages", "diff")})
        if verb == "wait":
            if event:
                event.wait(300)
            return self.reply(204)
        with LOCK:
            if verb == "interrupt":
                RUNS.setdefault(sid, {})["interrupted"] = True
                return self.reply(200, {"interrupted": True})
            if verb == "permission" and pid:
                owner = next((r["sessionID"] for run in RUNS.values() for r in run.get("pending", [])
                              if r["id"] == pid), None)
                if owner != sid:
                    return self.reply(404, {})
                for run in RUNS.values():
                    if any(r["id"] == pid for r in run.get("pending", [])):
                        run["reply"] = body
                root = next((s for s, run in RUNS.items() if run.get("reply") is body), sid)
                note(load(), root, reply={"id": pid, "session": sid, **body})
                return self.reply(204)
            if verb == "message":
                messages = sorted(session.get("messages", []), key=lambda m: -m["time"]["created"])
                if params.get("type"):
                    messages = [m for m in messages if m["type"] == params["type"]]
                return self.reply(200, messages[:int(params.get("limit", 50))])
            if verb == "diff":
                return self.reply(200, session.get("diff", []) if params.get("from") == session.get("diff_for") else [])
            return self.reply(404, {})

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")

    def do_PATCH(self):
        self.handle_any("PATCH")


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
print(f"opencode server listening on http://127.0.0.1:{server.server_address[1]}", flush=True)
server.serve_forever()
