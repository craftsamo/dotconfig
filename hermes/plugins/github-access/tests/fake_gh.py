"""A fake ``gh`` for the github-access tests: answers ``gh api graphql`` by matching the query text.

``rules`` is a list of (pattern, answer) where ``pattern`` is a regex searched in the query and
``answer`` is the ``data`` dict, a callable (variables -> data), or an Exception to raise as GraphQL
errors. Every call is recorded with its query and variables.
"""

from __future__ import annotations

import json
import re
import subprocess


class FakeGh:
    """``rules`` answer GraphQL by query; ``commands`` answer every other ``gh`` call by a regex on
    its space-joined argv, with stdout text, a callable (argv, stdin) -> text, or an Exception (exit 1)."""

    def __init__(self, rules=None):
        self.rules = list(rules or [])
        self.commands: list[tuple[str, object]] = []
        self.calls: list[dict] = []
        self.argv: list[list[str]] = []
        self.stdin: list[str | None] = []

    def add(self, pattern, answer):
        self.rules.insert(0, (pattern, answer))
        return self

    def cmd(self, pattern, answer=""):
        self.commands.insert(0, (pattern, answer))
        return self

    def ran(self, pattern):
        return [a for a in self.argv if re.search(pattern, " ".join(a))]

    def __call__(self, argv, stdin=None, timeout=None):
        self.argv.append(list(argv))
        self.stdin.append(stdin)
        if argv[:2] != ["api", "graphql"]:
            line = " ".join(argv)
            for pattern, answer in self.commands:
                if re.search(pattern, line):
                    if isinstance(answer, Exception):
                        return subprocess.CompletedProcess(argv, 1, "", str(answer))
                    out = answer(argv, stdin) if callable(answer) else answer
                    return subprocess.CompletedProcess(argv, 0, out if isinstance(out, str) else json.dumps(out), "")
            return subprocess.CompletedProcess(argv, 1, "", f"fake gh: no rule for {line}")
        body = json.loads(stdin or "{}")
        query, variables = body.get("query", ""), body.get("variables") or {}
        self.calls.append({"query": query, "variables": variables})
        for pattern, answer in self.rules:
            if re.search(pattern, query):
                if isinstance(answer, Exception):
                    return subprocess.CompletedProcess(argv, 1, json.dumps({"errors": [{"message": str(answer)}]}), "")
                data = answer(variables) if callable(answer) else answer
                return subprocess.CompletedProcess(argv, 0, json.dumps({"data": data}), "")
        return subprocess.CompletedProcess(argv, 1, "", f"fake gh: no rule for query {query[:80]}")

    def queries(self, pattern):
        return [c for c in self.calls if re.search(pattern, c["query"])]


def viewer(login="me"):
    return (r"^query\{viewer\{login\}\}$", {"viewer": {"login": login}})


def repo(name, owner_type="User", private=True, permission="ADMIN"):
    owner, short = name.split("/")

    def answer(v):
        if v.get("owner") != owner or v.get("name") != short:
            return {"repository": None}
        return {"repository": {"id": f"R_{short}", "nameWithOwner": name, "isPrivate": private, "isArchived": False,
                               "viewerPermission": permission, "owner": {"__typename": owner_type, "login": owner}}}
    return answer


def repos(*answers):
    def answer(v):
        for a in answers:
            got = a(v)
            if got["repository"]:
                return got
        return {"repository": None}
    return (r"viewerPermission owner\{__typename login\}", answer)


def member(orgs):
    return (r"viewerIsAMember", lambda v: {"organization": {"viewerIsAMember": v["login"] in orgs}})


def owner_types(types):
    return (r"repositoryOwner\(login:\$login\)\{__typename\}",
            lambda v: {"repositoryOwner": {"__typename": types[v["login"]]} if v["login"] in types else None})


def board(owner, number, title="Roadmap", owner_type="User", public=False, can_update=True, closed=False):
    return {"id": f"PVT_{owner}_{number}", "number": number, "title": title,
            "url": f"https://github.com/{'orgs' if owner_type == 'Organization' else 'users'}/{owner}/projects/{number}",
            "closed": closed, "public": public, "viewerCanUpdate": can_update,
            "owner": {"__typename": owner_type, "login": owner}}


def linked(boards):
    return (r"repository\(owner:\$owner,name:\$name\)\{projectsV2\(first:20\)",
            {"repository": {"projectsV2": {"nodes": boards}}})


def viewer_boards(boards):
    return (r"viewer\{projectsV2", {"viewer": {"projectsV2": {"nodes": boards}}})


def owner_boards(root, boards):
    return (rf"{root}\(login:\$login\)\{{projectsV2\(first:20", {root: {"projectsV2": {"nodes": boards}}})
