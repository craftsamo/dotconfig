"""The shared OpenCode service at the level of `api.call`, for the plugin's tests."""

import json
import threading
import urllib.parse

PERSON_DENIES = [{"action": "shell", "resource": "sudo *", "effect": "deny"},
                 {"action": "external_directory", "resource": "/secret/*", "effect": "deny"}]
PINS = {
    "plan": {"providerID": "anthropic", "id": "claude-opus-5-5", "variant": "high"},
    "review": {"providerID": "anthropic", "id": "claude-opus-5-5", "variant": "high"},
    "debug": {"providerID": "anthropic", "id": "claude-opus-5-5", "variant": "high"},
    "build": {"providerID": "anthropic", "id": "claude-opus-5-5", "variant": "medium"},
}


def agent_info(name):
    """What the service reports for an installed agent: base + global rules, then the person's."""
    base = [{"action": "*", "resource": "*", "effect": "allow"},
            {"action": "external_directory", "resource": "*", "effect": "ask"}]
    return {"id": name, "mode": "primary", "hidden": False, "permissions": base + PERSON_DENIES,
            "model": PINS[name], "description": f"{name} mode"}


class Fake:
    """Scripts per session drive a turn: one step is consumed each time the service is
    asked which sessions are active."""

    def __init__(self, directory, api):
        self.api = api
        self.directory = str(directory)
        self.sessions, self.messages, self.inbox, self.entries = {}, {}, {}, {}
        self.active, self.requests, self.forms = set(), [], []
        self.replies, self.answers, self.cancelled = [], [], []
        self.steers, self.prompts, self.calls, self.scripts = [], [], [], {}
        self.agents = {}
        self.down = False
        self.note_refused = False
        self.move_refused, self.moves = False, []
        self.prompt_error = None
        self.drop_permissions = False
        self.clock = 1_000_000
        tools = {"capabilities": {"tools": True}, "enabled": True}
        self.models = [
            {"providerID": "anthropic", "id": "claude-opus-5-5", "variants": [{"id": "high"}, {"id": "medium"}],
             **tools},
            {"providerID": "anthropic", "id": "claude-opus-5-5-fast", "variants": [{"id": "high"}], **tools},
            {"providerID": "anthropic", "id": "claude-fable-5-1", "variants": [{"id": "high"}], **tools},
            {"providerID": "openai", "id": "gpt-6.1-sol", "variants": [{"id": "medium"}, {"id": "high"}],
             "cost": [{"input": 2, "output": 10}], "limit": {"context": 400000}, **tools},
            {"providerID": "openai", "id": "gpt-6-sol", "variants": [{"id": "high"}], **tools},
            {"providerID": "openai", "id": "gpt-image-3", "variants": [], "capabilities": {"tools": False}},
            {"providerID": "xai", "id": "grok-4.7", "variants": [], **tools},
        ]
        self.lock = threading.RLock()

    def tick(self):
        self.clock += 10
        return self.clock

    # -- scripting
    def append(self, sid, message):
        self.messages[sid].append(message)

    def finish(self, sid, outcome="succeeded", text="RESULT_OK", error=None):
        """The turn ends: its assistant message, then the idle marker that closes it."""
        with self.lock:
            self.active.discard(sid)
            now = self.tick()
            message = {"id": f"msg_a{now}", "type": "assistant", "model": self.sessions[sid].get("model"),
                       "content": [{"type": "text", "text": text}] if text else []}
            if error:
                message["error"] = {"type": "provider.error", "message": error}
            self.append(sid, message)
            self.append(sid, {"id": f"msg_i{self.tick()}", "type": "idle", "outcome": outcome})
            self.sessions[sid]["time"]["idle"] = self.clock

    def retry(self, sid, message, attempt):
        """OpenCode sitting in a provider retry: the newest assistant message carries it."""
        with self.lock:
            last = self.messages[sid][-1] if self.messages[sid] else {}
            if last.get("type") != "assistant":
                last = {"id": f"msg_a{self.tick()}", "type": "assistant",
                        "model": self.sessions[sid].get("model"), "content": []}
                self.append(sid, last)
            last["retry"] = {"attempt": attempt, "at": self.clock + 60_000,
                             "error": {"type": "provider.error", "message": message}}

    def ask(self, sid, action="external_directory", resources=("/elsewhere/*",), save=("/elsewhere/*",)):
        with self.lock:
            request = {"id": f"per_{len(self.requests) + len(self.replies)}x", "sessionID": sid, "action": action,
                       "resources": list(resources), "save": list(save)}
            self.requests.append(request)
            return request

    def question(self, sid):
        with self.lock:
            form = {"id": f"frm_{len(self.forms) + len(self.answers) + len(self.cancelled)}x", "sessionID": sid,
                    "title": "Questions", "metadata": {"kind": "question"},
                    "fields": [{"key": "q0", "title": "Color", "description": "Red or blue?", "type": "string",
                                "options": [{"value": "Red", "label": "Red"}, {"value": "Blue", "label": "Blue"}],
                                "custom": True}]}
            self.forms.append(form)
            return form

    def child(self, sid):
        child = f"{sid}child"
        self.sessions[child] = {"id": child, "parentID": sid, "agent": "explore", "permissions": [],
                                "location": {"directory": self.directory}, "time": {"created": self.tick()}}
        self.messages[child] = []
        return child

    def _paused(self, sid):
        related = {sid} | {s for s, v in self.sessions.items() if v.get("parentID") == sid}
        return any(r["sessionID"] in related for r in self.requests) or \
            any(f["sessionID"] in related for f in self.forms)

    def _step(self, sid):
        script = self.scripts.get(sid)
        if not script:
            return
        step = script.pop(0)
        if step == "hold":
            script.insert(0, "hold")
        elif step.startswith("finish"):
            _, outcome, text = (step.split(":", 2) + ["succeeded", "RESULT_OK"])[:3]
            self.finish(sid, outcome or "succeeded", text if text != "" else "")
        elif step == "vanish":
            self.active.discard(sid)
        elif step == "down":
            self.down = True
        elif step.startswith("fail-error:"):
            self.finish(sid, "failed", "", step.split(":", 1)[1])
        elif step.startswith("retry:"):
            _, message, attempt = step.split(":", 2)
            self.retry(sid, message, int(attempt))
        elif step == "ask-permission":
            self.ask(sid)
            script.insert(0, "wait-reply")
        elif step == "ask-question":
            self.question(sid)
            script.insert(0, "wait-reply")
        elif step == "ask-child":
            self.ask(self.child(sid))
            script.insert(0, "wait-reply")
        elif step == "wait-reply":
            if self._paused(sid):
                script.insert(0, "wait-reply")

    # -- api.call
    def __call__(self, method, route, data=None, **kwargs):
        with self.lock:
            self.calls.append((method, route, data))
            if self.down:
                raise self.api.Unavailable("service down")
            parsed = urllib.parse.urlsplit(route)
            query = dict(urllib.parse.parse_qsl(parsed.query))
            parts = [urllib.parse.unquote(p) for p in parsed.path.strip("/").split("/")[1:]]
            return self._route(method, parts, query, data)

    def _session(self, sid):
        if sid not in self.sessions:
            raise self.api.ApiError(404, "SessionNotFoundError", "Session not found")
        return self.sessions[sid]

    def _route(self, method, parts, query, data):
        if parts == ["info"]:
            return {"version": "2.0.23", "paths": {"tmp": "/tmp/fake-opencode"}}
        if parts == ["model"]:
            return {"data": self.models}
        if parts == ["agent"]:
            return {"data": [self.agents.get(n) or agent_info(n) for n in PINS]}
        if parts[0] == "agent":
            if parts[1] not in PINS and parts[1] not in self.agents:
                raise self.api.ApiError(404, "AgentNotFoundError", "no such agent")
            return {"data": self.agents.get(parts[1]) or agent_info(parts[1])}
        if parts == ["skill"]:
            return {"data": [{"id": "git-commit", "name": "git-commit", "description": "d", "path": "/p"}]}
        if parts == ["command"]:
            return {"data": []}
        if parts == ["vcs", "status"]:
            return {"data": [{"file": "a.py", "status": "modified"}]}
        if parts == ["permission", "request"]:
            assert query.get("location[directory]") == self.directory
            return {"location": {"directory": self.directory}, "data": [dict(r) for r in self.requests]}
        if parts == ["form"]:
            assert query.get("location[directory]") == self.directory
            return {"location": {"directory": self.directory}, "data": [json.loads(json.dumps(f)) for f in self.forms]}
        if parts == ["session", "active"]:
            for sid in list(self.active):
                self._step(sid)
            return {"data": {sid: {"type": "running"} for sid in self.active}}
        if parts == ["session"] and method == "get":
            items = [s for s in self.sessions.values()
                     if not query.get("directory") or s["location"]["directory"] == query["directory"]]
            return {"data": json.loads(json.dumps(list(reversed(items)))), "cursor": {}}
        if parts == ["session"] and method == "post":
            sid = f"ses_{len(self.sessions) + 1}abc"
            self.sessions[sid] = {"id": sid, "agent": data["agent"], "model": data["model"],
                                  "permissions": [] if self.drop_permissions else data["permissions"],
                                  "metadata": data.get("metadata"), "title": data.get("title"),
                                  "location": {"directory": data["location"]["directory"]},
                                  "tokens": {"input": 1, "output": 2},
                                  "time": {"created": self.tick(), "updated": self.clock}}
            self.messages[sid] = []
            return {"data": self.sessions[sid]}
        if parts[0] == "experimental":
            sid, rest = parts[2], parts[3:]
            self._session(sid)
            entries = self.entries.setdefault(sid, {})
            if rest == ["instructions", "entries"]:
                return {"data": [{"key": k, "value": v} for k, v in entries.items()]}
            if rest[:2] == ["instructions", "entries"] and method == "put":
                if self.note_refused:
                    raise self.api.ApiError(404, "NotFound", "no such route")
                entries[rest[2]] = data["value"]
                return None
            if rest[:2] == ["instructions", "entries"] and method == "delete":
                entries.pop(rest[2], None)
                return None
            raise AssertionError(f"unrouted {method} {parts}")
        sid = parts[1]
        session = self._session(sid)
        rest = parts[2:]
        if not rest and method == "get":
            return {"data": json.loads(json.dumps(session))}
        if not rest and method == "patch":
            session.update(data)
            return {"data": session}
        if rest == ["fork"]:
            new = f"ses_{len(self.sessions) + 1}fork"
            self.sessions[new] = {**json.loads(json.dumps(session)), "id": new, "time": {"created": self.tick()}}
            self.messages[new] = list(self.messages[sid])
            return {"data": self.sessions[new]}
        if rest == ["move"]:
            if self.move_refused:
                raise self.api.ApiError(400, "DestinationUnavailableError", "no such directory")
            self.moves.append((sid, data["directory"]))
            session["location"] = {"directory": data["directory"]}
            return None
        if rest == ["agent"]:
            session["agent"] = data["agent"]
            return None
        if rest == ["model"]:
            session["model"] = data["model"]
            return None
        if rest == ["prompt"]:
            if self.prompt_error and data.get("delivery") != "steer":
                raise self.prompt_error
            now = self.tick()
            mid = f"msg_u{now}"
            if data.get("delivery") == "steer":
                self.steers.append((sid, data["text"]))
                self.inbox.setdefault(sid, []).append({"id": mid})
            else:
                self.prompts.append((sid, data["text"]))
                self.append(sid, {"id": mid, "type": "user", "text": data["text"]})
                self.active.add(sid)
                if not self.scripts.get(sid):
                    self.scripts[sid] = ["finish"]
            return {"data": {"id": mid, "time": {"created": now}, "type": "user"}}
        if rest == ["interrupt"]:
            was = sid in self.active
            for other in [s for s in self.active if s == sid or self.sessions[s].get("parentID") == sid]:
                self.finish(other, "interrupted", "")
            self.scripts.pop(sid, None)
            return {"interrupted": was}
        if rest == ["inbox"]:
            return {"data": self.inbox.get(sid, [])}
        if rest[:1] == ["inbox"] and method == "delete":
            self.inbox[sid] = [i for i in self.inbox.get(sid, []) if i["id"] != rest[1]]
            return None
        if rest == ["message"]:
            return {"data": list(reversed(self.messages[sid])), "cursor": {}}
        if rest == ["diff"]:
            return {"data": [{"file": "a.py", "status": "modified", "additions": 3, "deletions": 1,
                              "patch": "x" * 100}]}
        if rest[:1] == ["permission"] and rest[-1] == "reply":
            request = next((r for r in self.requests if r["id"] == rest[1]), None)
            if request is None:
                raise self.api.ApiError(404, "PermissionNotFoundError", "not pending")
            self.requests.remove(request)
            self.replies.append((rest[1], data))
            return None
        if rest[:1] == ["form"] and len(rest) == 3 and rest[-1] == "reply":
            form = next((f for f in self.forms if f["id"] == rest[1]), None)
            if form is None:
                raise self.api.ApiError(404, "FormNotFoundError", "not pending")
            self.forms.remove(form)
            self.answers.append((rest[1], data))
            return None
        if rest[:1] == ["form"] and len(rest) == 2 and method == "delete":
            form = next((f for f in self.forms if f["id"] == rest[1]), None)
            if form is None:
                raise self.api.ApiError(404, "FormNotFoundError", "not pending")
            self.forms.remove(form)
            self.cancelled.append(rest[1])
            return None
        raise AssertionError(f"unrouted {method} {parts}")
