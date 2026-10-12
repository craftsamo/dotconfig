"""Workspace registry engine: people, projects, memberships and repos as CSV files.

The data lives in ``<Workspaces>/.registry/*.csv`` (see README.md for the model).
Stdlib only; loaded by the ``workspace_registry`` Hermes tool (``__init__.py``) and
by the ``wsreg`` CLI, so both run the same code.

Entry point: ``run(args, root=None) -> dict``. ``args`` is the tool's JSON
(``action`` plus parameters). Errors raise ``RegistryError``.
"""

from __future__ import annotations

import contextlib
import csv
from datetime import date
import fcntl
import importlib.util
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

REGISTRY_DIR = ".registry"

TABLES = {
    "persons": ("id", "display_name", "kind", "status", "review_status", "residence_country",
                "preferred_language", "preferred_contact_channel", "timezone"),
    "person_aliases": ("person_id", "alias", "is_primary"),
    "person_contacts": ("person_id", "channel", "handle", "is_primary"),
    "person_languages": ("person_id", "language", "proficiency", "is_primary"),
    "person_nationalities": ("person_id", "country", "is_primary"),
    "person_notes": ("person_id", "date", "text"),
    "projects": ("id", "slug", "canonical_name", "kind", "status", "organization_id", "summary",
                 "review_status"),
    "project_aliases": ("project_id", "alias", "is_primary"),
    "project_links": ("project_id", "kind", "url", "label"),
    "project_tags": ("project_id", "axis", "value"),
    "tag_axes": ("axis", "label"),
    "repos": ("project_id", "name", "owner", "host", "url", "ghq_path", "summary", "status",
              "review_status"),
    "memberships": ("project_id", "person_id", "status", "working_relationship", "can_merge",
                    "can_deploy"),
    "membership_roles": ("project_id", "person_id", "role"),
    "membership_responsibilities": ("project_id", "person_id", "responsibility"),
    "membership_areas": ("project_id", "person_id", "area"),
    "membership_notes": ("project_id", "person_id", "text"),
}

REVIEW = ("needs_review", "confirmed", "ignored")
CHANNELS = ("github", "telegram", "x", "website", "signal", "matrix", "discord", "linkedin", "email", "phone")
PERSON_KINDS = ("self", "individual")
PERSON_STATUS = ("active", "inactive")
PROJECT_KINDS = ("org", "client", "category", "personal", "external")
PROJECT_STATUS = ("active", "inactive", "archived")
REPO_STATUS = ("declared", "linked", "missing", "archived")
MEMBER_STATUS = ("active", "inactive")
LINK_KINDS = ("landing", "x", "github", "docs", "discord", "other")
PROFICIENCY = ("native", "fluent", "conversational", "basic")

ENUMS = {
    ("persons", "kind"): PERSON_KINDS,
    ("persons", "status"): PERSON_STATUS,
    ("persons", "review_status"): REVIEW,
    ("persons", "preferred_contact_channel"): CHANNELS,
    ("person_contacts", "channel"): CHANNELS,
    ("person_languages", "proficiency"): PROFICIENCY,
    ("projects", "kind"): PROJECT_KINDS,
    ("projects", "status"): PROJECT_STATUS,
    ("projects", "review_status"): REVIEW,
    ("project_links", "kind"): LINK_KINDS,
    ("repos", "status"): REPO_STATUS,
    ("repos", "review_status"): REVIEW,
    ("memberships", "status"): MEMBER_STATUS,
}
PATTERNS = {
    ("persons", "id"): (r"[a-z0-9][a-z0-9_]*", "a bare lowercase slug"),
    ("persons", "residence_country"): (r"[A-Z]{2}", "an ISO 3166-1 alpha-2 code"),
    ("persons", "preferred_language"): (r"[a-z]{2,3}", "an ISO 639 code"),
    ("person_languages", "language"): (r"[a-z]{2,3}", "an ISO 639 code"),
    ("person_nationalities", "country"): (r"[A-Z]{2}", "an ISO 3166-1 alpha-2 code"),
    ("person_notes", "date"): (r"\d{4}-\d{2}-\d{2}", "YYYY-MM-DD"),
    ("projects", "id"): (r"[A-Za-z0-9][A-Za-z0-9._-]*", "a directory name"),
    ("projects", "slug"): (r"[a-z0-9]+(?:-[a-z0-9]+)*", "lower-kebab"),
    ("tag_axes", "axis"): (r"[a-z][a-z0-9_]*", "a lowercase identifier"),
    ("repos", "name"): (r"(?!\.\.?$)[A-Za-z0-9._-]+", "a repo name (no slash, not . or ..)"),
    ("repos", "owner"): (r"(?!\.\.?$)[A-Za-z0-9._-]+", "an owner name (no slash, not . or ..)"),
    ("repos", "host"): (r"[a-z0-9]+(?:[.-][a-z0-9]+)*(?::\d+)?", "a host name"),
    ("repos", "ghq_path"): (r"(?:~|/).*", "an absolute or ~ path"),
}
REQUIRED = {
    "persons": ("id", "display_name", "kind", "status", "review_status"),
    "person_aliases": ("person_id", "alias"),
    "person_contacts": ("person_id", "channel", "handle"),
    "person_languages": ("person_id", "language"),
    "person_nationalities": ("person_id", "country"),
    "person_notes": ("person_id", "text"),
    "projects": ("id", "slug", "canonical_name", "kind", "status", "review_status"),
    "project_aliases": ("project_id", "alias"),
    "project_links": ("project_id", "kind", "url"),
    "project_tags": ("project_id", "axis", "value"),
    "tag_axes": ("axis", "label"),
    "repos": ("project_id", "name", "host", "status", "review_status"),
    "memberships": ("project_id", "person_id", "status"),
    "membership_roles": ("project_id", "person_id", "role"),
    "membership_responsibilities": ("project_id", "person_id", "responsibility"),
    "membership_areas": ("project_id", "person_id", "area"),
    "membership_notes": ("project_id", "person_id", "text"),
}
BOOLS = {("person_aliases", "is_primary"), ("person_contacts", "is_primary"),
         ("person_languages", "is_primary"), ("person_nationalities", "is_primary"),
         ("project_aliases", "is_primary"), ("memberships", "can_merge"), ("memberships", "can_deploy")}
TRUE, FALSE = "true", "false"
BOOL_WORDS = {"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False, "": False}

MEMBER_LISTS = {"roles": ("membership_roles", "role"),
                "responsibilities": ("membership_responsibilities", "responsibility"),
                "areas": ("membership_areas", "area"),
                "notes": ("membership_notes", "text")}
PERSON_FACETS = ("alias", "contact", "language", "nationality", "note")
PROJECT_FACETS = ("alias", "link", "tag")


class RegistryError(Exception):
    pass


# --------------------------------------------------------------------------- normalization
def norm(s) -> str:
    s = unicodedata.normalize("NFKC", s or "").casefold()
    return re.sub(r"\s+", " ", s).strip()


def norm_handle(s) -> str:
    n = norm(s)
    n = re.sub(r"^(https?://)?(www\.)?(t\.me/|x\.com/|twitter\.com/|github\.com/)", "", n)
    return n.lstrip("@").strip("/")


def kebab(s) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "unnamed"


def truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    word = str(v if v is not None else "").strip().lower()
    if word not in BOOL_WORDS:
        raise RegistryError(f"not a boolean: {v!r}")
    return BOOL_WORDS[word]


def flag(v) -> bool:
    """Lenient read of a stored boolean (validate reports bad words; views never crash)."""
    return BOOL_WORDS.get(str(v or "").strip().lower(), False)


def boolcell(v) -> str:
    return TRUE if truthy(v) else FALSE


def key_of(table, r):
    """Uniqueness key of a row, or None for tables that allow repeats (notes)."""
    k = {
        "persons": lambda: (r["id"],),
        "person_aliases": lambda: (r["person_id"], norm(r["alias"])),
        "person_contacts": lambda: (r["person_id"], r["channel"], norm_handle(r["handle"])),
        "person_languages": lambda: (r["person_id"], r["language"]),
        "person_nationalities": lambda: (r["person_id"], r["country"]),
        "projects": lambda: (r["id"],),
        "project_aliases": lambda: (r["project_id"], norm(r["alias"])),
        "project_links": lambda: (r["project_id"], r["kind"], r["url"]),
        "project_tags": lambda: (r["project_id"], r["axis"], norm(r["value"])),
        "tag_axes": lambda: (r["axis"],),
        "repos": lambda: (r["project_id"], r["name"]),
        "memberships": lambda: (r["project_id"], r["person_id"]),
        "membership_roles": lambda: (r["project_id"], r["person_id"], r["role"]),
        "membership_responsibilities": lambda: (r["project_id"], r["person_id"], r["responsibility"]),
        "membership_areas": lambda: (r["project_id"], r["person_id"], r["area"]),
    }.get(table)
    return k() if k else None


ORDERED = {"person_notes", "membership_roles", "membership_responsibilities", "membership_areas",
           "membership_notes"}  # rows keep their order within one owner


def sort_key(table, r):
    if table in ORDERED:
        owner = ("project_id", "person_id") if table.startswith("membership_") else ("person_id",)
        return tuple(r[c].casefold() for c in owner)  # sorted() is stable
    return tuple(str(x).casefold() for x in key_of(table, r))


def primary_first(items, col):
    return sorted(items, key=lambda x: (not x["is_primary"], x[col]))


def default_root() -> Path:
    return Path(os.environ.get("WSREG_ROOT") or Path.home() / "Workspaces").expanduser()


def data_dir(root) -> Path:
    """<root>/.registry, or $WSREG_DIR (staging: live paths, other data)."""
    env = os.environ.get("WSREG_DIR")
    return Path(env).expanduser() if env else Path(root).expanduser() / REGISTRY_DIR


def ghq_root() -> Path:
    return Path(os.environ.get("GHQ_ROOT") or Path.home() / "ghq").expanduser()


def contract_home(p) -> str:
    p = str(p)
    home = str(Path.home())
    return "~" + p[len(home):] if p == home or p.startswith(home + os.sep) else p


# --------------------------------------------------------------------------- storage
class Registry:
    def __init__(self, root):
        self.root = Path(root).expanduser()
        self.dir = data_dir(self.root)
        self.t = {name: [] for name in TABLES}
        self.load_errors = []
        self.before_errs = []

    @classmethod
    def load(cls, root=None):
        reg = cls(root or default_root())
        if not reg.dir.is_dir():
            raise RegistryError(f"no registry at {reg.dir}")
        for name, cols in TABLES.items():
            path = reg.dir / f"{name}.csv"
            if not path.exists():
                continue
            try:
                reg._read(name, cols, path)
            except (UnicodeDecodeError, csv.Error, ValueError) as exc:
                reg.t[name] = []
                reg.load_errors.append(f"{name}.csv: unreadable ({exc}); save it as UTF-8 CSV")
        return reg

    def _read(self, name, cols, path):
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            missing = [c for c in cols if c not in header]
            extra = [c for c in header if c not in cols]
            if missing:
                self.load_errors.append(f"{name}.csv: missing column(s) {', '.join(missing)}")
            if extra:
                self.load_errors.append(f"{name}.csv: unknown column(s) {', '.join(extra)}")
            for line, raw in enumerate(reader, start=2):
                if None in raw:
                    self.load_errors.append(f"{name}.csv line {line}: more cells than columns")
                row = {c: (raw.get(c) or "").strip() for c in cols}
                if any(row.values()):
                    self.t[name].append(row)

    def save(self, tables):
        """Write every table to a synced temp file first, then rename them all in one go."""
        temps = []
        try:
            for name in tables:
                rows = sorted(self.t[name], key=lambda r: sort_key(name, r))
                self.t[name] = rows
                fd, tmp = tempfile.mkstemp(prefix=f".{name}.", suffix=".tmp", dir=self.dir)
                temps.append((tmp, self.dir / f"{name}.csv"))
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=TABLES[name], lineterminator="\n")
                    w.writeheader()
                    w.writerows(rows)
                    f.flush()
                    os.fsync(f.fileno())
            for tmp, dest in temps:
                os.replace(tmp, dest)
        finally:
            for tmp, _ in temps:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(tmp)

    # ---- lookups
    def rows(self, table, **match):
        return [r for r in self.t[table] if all(r[k] == v for k, v in match.items())]

    def one(self, table, **match):
        found = self.rows(table, **match)
        return found[0] if found else None

    def person(self, pid):
        r = self.one("persons", id=pid)
        if not r:
            raise RegistryError(f"no person {pid!r}")
        return r

    def project(self, pid):
        r = self.one("projects", id=pid)
        if not r:
            raise RegistryError(f"no project {pid!r}")
        return r

    def delete(self, table, **match):
        before = len(self.t[table])
        self.t[table] = [r for r in self.t[table] if not all(r[k] == v for k, v in match.items())]
        return before - len(self.t[table])

    # ---- derived paths
    def dir_path(self, project_id):
        d = self.root / "Projects" / project_id
        return str(d) if d.is_dir() else None

    def default_ghq(self, repo):
        if not repo["owner"]:
            return None
        return str(ghq_root() / (repo["host"] or "github.com") / repo["owner"] / repo["name"])

    def ghq_path(self, repo):
        return str(Path(repo["ghq_path"]).expanduser()) if repo["ghq_path"] else self.default_ghq(repo)

    def link_path(self, repo):
        d = self.dir_path(repo["project_id"])
        return str(Path(d) / "github" / repo["name"]) if d else None

    # ---- validation
    def check(self):
        """(errors, warnings) — deterministic strings."""
        errs = list(self.load_errors)
        warns = []
        for table, cols in TABLES.items():
            seen = {}
            for r in self.t[table]:
                where = f"{table}[{', '.join(r[c] for c in cols[:2] if r[c])}]"
                for c in REQUIRED.get(table, ()):
                    if not r[c]:
                        errs.append(f"{where}: {c} is empty")
                for c in cols:
                    v = r[c]
                    if not v:
                        continue
                    if (table, c) in ENUMS and v not in ENUMS[(table, c)]:
                        errs.append(f"{where}: {c} {v!r} is not one of {'|'.join(ENUMS[(table, c)])}")
                    if (table, c) in PATTERNS:
                        pat, what = PATTERNS[(table, c)]
                        if not re.fullmatch(pat, v):
                            errs.append(f"{where}: {c} {v!r} is not {what}")
                    if (table, c) in BOOLS and v.lower() not in BOOL_WORDS:
                        errs.append(f"{where}: {c} {v!r} is not true/false")
                k = key_of(table, r)
                if k is not None and all(k):
                    if k in seen:
                        errs.append(f"{where}: duplicate {table} row")
                    seen[k] = True
        persons = {r["id"] for r in self.t["persons"]}
        projects = {r["id"]: r for r in self.t["projects"]}
        members = {(r["project_id"], r["person_id"]) for r in self.t["memberships"]}
        for r in self.t["persons"]:
            if r["timezone"] and ZoneInfo is not None:
                try:
                    ZoneInfo(r["timezone"])
                except Exception:
                    errs.append(f"persons[{r['id']}]: timezone {r['timezone']!r} is not an IANA name")
        if sum(1 for r in self.t["persons"] if r["kind"] == "self") > 1:
            errs.append("persons: more than one person of kind self")
        for table in ("person_aliases", "person_contacts", "person_languages", "person_nationalities",
                      "person_notes"):
            for r in self.t[table]:
                if r["person_id"] and r["person_id"] not in persons:
                    errs.append(f"{table}: unknown person {r['person_id']!r}")
        for table in ("project_aliases", "project_links", "project_tags", "repos", "memberships"):
            for r in self.t[table]:
                if r["project_id"] and r["project_id"] not in projects:
                    errs.append(f"{table}: unknown project {r['project_id']!r}")
        for r in self.t["memberships"]:
            if r["person_id"] and r["person_id"] not in persons:
                errs.append(f"memberships[{r['project_id']}, {r['person_id']}]: unknown person")
        for table, _col in MEMBER_LISTS.values():
            for r in self.t[table]:
                if (r["project_id"], r["person_id"]) not in members:
                    errs.append(f"{table}: no membership {r['project_id']}/{r['person_id']}")
        for r in projects.values():
            org = r["organization_id"]
            if not org:
                continue
            if org == r["id"]:
                errs.append(f"projects[{r['id']}]: a project cannot be its own organization")
            elif org not in projects:
                errs.append(f"projects[{r['id']}]: unknown organization {org!r}")
            elif projects[org]["kind"] != "org":
                errs.append(f"projects[{r['id']}]: organization {org!r} is not kind=org")
        for table, owner in (("person_aliases", "person_id"), ("person_contacts", "person_id"),
                             ("person_languages", "person_id"), ("person_nationalities", "person_id"),
                             ("project_aliases", "project_id")):
            count = {}
            for r in self.t[table]:
                if r["is_primary"].lower() in ("true", "1", "yes"):
                    count[r[owner]] = count.get(r[owner], 0) + 1
            for oid, n in sorted(count.items()):
                if n > 1:
                    errs.append(f"{table}: {oid} has {n} primary rows")
        for table, owner in (("person_aliases", "person_id"), ("project_aliases", "project_id")):
            by = {}
            for r in self.t[table]:
                by.setdefault(norm(r["alias"]), set()).add(r[owner])
            for a, owners in sorted(by.items()):
                if len(owners) > 1:
                    warns.append(f"{table}: alias {a!r} is shared by {', '.join(sorted(owners))}")
        axes = {r["axis"] for r in self.t["tag_axes"]}
        for axis in sorted({r["axis"] for r in self.t["project_tags"]} - axes):
            warns.append(f"project_tags: axis {axis!r} has no row in tag_axes.csv")
        pdir = self.root / "Projects"
        if pdir.is_dir():
            for d in sorted(pdir.iterdir()):
                if d.is_dir() and not d.name.startswith(".") and d.name not in projects:
                    warns.append(f"Projects/{d.name} has no registry row")
        for r in projects.values():
            if r["kind"] == "external" and self.dir_path(r["id"]):
                warns.append(f"projects[{r['id']}]: kind external but Projects/{r['id']} exists")
        return errs, warns


@contextlib.contextmanager
def transaction(root=None):
    """Lock, load, yield the registry, then validate and write the changed tables.

    Rejects the change if it adds a validation error; pre-existing errors do not block."""
    root = Path(root or default_root()).expanduser()
    d = data_dir(root)
    if not d.is_dir():
        raise RegistryError(f"no registry at {d}")
    with open(d / ".lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        reg = Registry.load(root)
        if reg.load_errors:
            raise RegistryError("the registry files have structural errors; fix them before any write "
                                "(a write would drop the unreadable cells): " + "; ".join(reg.load_errors))
        before_errs, _ = reg.check()
        reg.before_errs = before_errs
        snapshot = {k: [dict(r) for r in v] for k, v in reg.t.items()}
        yield reg
        errs, _ = reg.check()
        added = [e for e in errs if e not in before_errs]
        if added:
            raise RegistryError("change rejected: " + "; ".join(added))
        reg.save([k for k in TABLES if reg.t[k] != snapshot[k]])


# --------------------------------------------------------------------------- views
def person_flat(r):
    return {c: (r[c] or None) for c in ("id", "display_name", "kind", "status", "review_status",
                                        "residence_country", "preferred_language")}


def membership_obj(reg, m, names=True):
    key = {"project_id": m["project_id"], "person_id": m["person_id"]}
    out = {**key, "status": m["status"] or None, "working_relationship": m["working_relationship"] or None,
           "can_merge": flag(m["can_merge"]), "can_deploy": flag(m["can_deploy"])}
    for field, (table, col) in MEMBER_LISTS.items():
        out[field] = [r[col] for r in reg.rows(table, **key)]
    if names:
        p = reg.one("persons", id=m["person_id"])
        pr = reg.one("projects", id=m["project_id"])
        out["person_name"] = p["display_name"] if p else None
        out["project_name"] = pr["canonical_name"] if pr else None
    return out


def person_obj(reg, pid):
    r = reg.person(pid)
    out = {c: (r[c] or None) for c in TABLES["persons"]}
    out["aliases"] = primary_first([{"alias": a["alias"], "is_primary": flag(a["is_primary"])}
                                    for a in reg.rows("person_aliases", person_id=pid)], "alias")
    out["contacts"] = primary_first([{"channel": c["channel"], "handle": c["handle"],
                                      "is_primary": flag(c["is_primary"])}
                                     for c in reg.rows("person_contacts", person_id=pid)], "channel")
    out["languages"] = primary_first([{"language": x["language"], "proficiency": x["proficiency"] or None,
                                       "is_primary": flag(x["is_primary"])}
                                      for x in reg.rows("person_languages", person_id=pid)], "language")
    out["nationalities"] = primary_first([{"country": x["country"], "is_primary": flag(x["is_primary"])}
                                          for x in reg.rows("person_nationalities", person_id=pid)], "country")
    out["notes"] = [{"date": n["date"] or None, "text": n["text"]} for n in reg.rows("person_notes", person_id=pid)]
    out["memberships"] = [membership_obj(reg, m) for m in reg.rows("memberships", person_id=pid)]
    return out


def repo_obj(reg, r):
    ghq = reg.ghq_path(r)
    return {"project_id": r["project_id"], "name": r["name"], "owner": r["owner"] or None,
            "host": r["host"] or "github.com", "url": r["url"] or None, "ghq_path": ghq,
            "link_path": reg.link_path(r), "has_agents_md": bool(ghq and (Path(ghq) / "AGENTS.md").exists()),
            "summary": r["summary"] or None, "status": r["status"], "review_status": r["review_status"]}


def project_obj(reg, pid, full=False):
    r = reg.project(pid)
    out = {c: (r[c] or None) for c in TABLES["projects"]}
    out["dir_path"] = reg.dir_path(pid)
    out["aliases"] = primary_first([{"alias": a["alias"], "is_primary": flag(a["is_primary"])}
                                    for a in reg.rows("project_aliases", project_id=pid)], "alias")
    out["links"] = [{"kind": x["kind"], "url": x["url"], "label": x["label"] or None}
                    for x in reg.rows("project_links", project_id=pid)]
    out["tags"] = [{"axis": x["axis"], "value": x["value"]} for x in reg.rows("project_tags", project_id=pid)]
    if full:
        out["repos"] = [repo_obj(reg, x) for x in reg.rows("repos", project_id=pid)]
        out["members"] = [membership_obj(reg, m) for m in reg.rows("memberships", project_id=pid)]
        if r["kind"] == "org":
            out["projects"] = [p["id"] for p in reg.rows("projects", organization_id=pid)]
    return out


# --------------------------------------------------------------------------- argument helpers
def need(a, key):
    v = a.get(key)
    if v in (None, ""):
        raise RegistryError(f"{a.get('action')}: {key} is required")
    return str(v).strip()


def fields_of(a, allowed):
    f = a.get("fields") or {}
    if not isinstance(f, dict):
        raise RegistryError("fields must be an object")
    unknown = sorted(set(f) - set(allowed))
    if unknown:
        raise RegistryError(f"unknown field(s) {', '.join(unknown)}; allowed: {', '.join(allowed)}")
    return f


def cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return TRUE if v else FALSE
    return str(v).strip()


def target(a, facets_person, facets_project):
    facet = need(a, "facet")
    person, project = a.get("person"), a.get("project")
    if bool(person) == bool(project):
        raise RegistryError("give exactly one of person or project")
    allowed = facets_person if person else facets_project
    if facet not in allowed:
        raise RegistryError(f"facet {facet!r} does not apply to a {'person' if person else 'project'}; "
                            f"use one of {', '.join(allowed)}")
    return facet, ("person" if person else "project"), str(person or project).strip()


# --------------------------------------------------------------------------- read actions
def a_whois(reg, a):
    q = need(a, "query")
    qn, hn = norm(q), norm_handle(q)
    ids = []

    def add(pid):
        if pid not in ids:
            ids.append(pid)

    if reg.one("persons", id=q):
        add(q)
    for c in reg.t["person_contacts"]:
        if norm_handle(c["handle"]) == hn:
            add(c["person_id"])
    for x in reg.t["person_aliases"]:
        if norm(x["alias"]) == qn:
            add(x["person_id"])
    for p in reg.t["persons"]:
        if norm(p["display_name"]) == qn:
            add(p["id"])
    if not ids and qn:
        for x in reg.t["person_aliases"]:
            if qn in norm(x["alias"]):
                add(x["person_id"])
        for c in reg.t["person_contacts"]:
            if hn and hn in norm_handle(c["handle"]):
                add(c["person_id"])
    return {"query": q, "matches": [person_obj(reg, pid) for pid in ids if reg.one("persons", id=pid)]}


def a_person(reg, a):
    return {"person": person_obj(reg, need(a, "id"))}


def a_persons(reg, a):
    rows = reg.t["persons"]
    if a.get("status"):
        rows = [r for r in rows if r["status"] == a["status"]]
    if a.get("kind"):
        rows = [r for r in rows if r["kind"] == a["kind"]]
    if a.get("project"):
        ids = {m["person_id"] for m in reg.rows("memberships", project_id=a["project"])}
        rows = [r for r in rows if r["id"] in ids]
    return {"persons": [person_flat(r) for r in sorted(rows, key=lambda r: r["id"])]}


def a_project(reg, a):
    return {"project": project_obj(reg, need(a, "id"), full=True)}


def a_projects(reg, a):
    rows = reg.t["projects"]
    for key, col in (("status", "status"), ("kind", "kind"), ("organization", "organization_id")):
        if a.get(key):
            rows = [r for r in rows if r[col] == a[key]]
    return {"projects": [project_obj(reg, r["id"]) for r in sorted(rows, key=lambda r: r["id"])]}


def a_members(reg, a):
    rows = reg.t["memberships"]
    if a.get("project"):
        rows = [m for m in rows if m["project_id"] == a["project"]]
    if a.get("person"):
        rows = [m for m in rows if m["person_id"] == a["person"]]
    return {"memberships": [membership_obj(reg, m) for m in rows]}


def a_repos(reg, a):
    rows = reg.t["repos"]
    if a.get("project"):
        rows = [r for r in rows if r["project_id"] == a["project"]]
    return {"repos": [repo_obj(reg, r) for r in rows]}


def a_search(reg, a):
    q = norm(need(a, "query"))
    persons, projects = [], []
    for p in reg.t["persons"]:
        hay = [p["id"], p["display_name"]] + [x["alias"] for x in reg.rows("person_aliases", person_id=p["id"])] \
            + [c["handle"] for c in reg.rows("person_contacts", person_id=p["id"])]
        if any(q in norm(h) for h in hay):
            persons.append(person_flat(p))
    for p in reg.t["projects"]:
        hay = [p["id"], p["slug"], p["canonical_name"], p["summary"]] \
            + [x["alias"] for x in reg.rows("project_aliases", project_id=p["id"])]
        if any(q in norm(h) for h in hay):
            projects.append({c: p[c] or None for c in ("id", "canonical_name", "kind", "status", "organization_id")})
    return {"query": a["query"], "persons": persons, "projects": projects}


def a_review(reg, a):
    return {"persons": [r["id"] for r in reg.t["persons"] if r["review_status"] == "needs_review"],
            "projects": [r["id"] for r in reg.t["projects"] if r["review_status"] == "needs_review"],
            "repos": [f"{r['project_id']}/{r['name']}" for r in reg.t["repos"] if r["review_status"] == "needs_review"]}


PEER_CHECKS = Path(__file__).resolve().with_name("peer_checks.py")


def peer_call(method, *args):
    """Run an installed local integration, never a path supplied by a tool call.

    Absence is normal on a standalone install; a broken installed link is not.
    Integration failures are warnings and must not roll back a registry write.
    """
    if not os.path.lexists(PEER_CHECKS):
        return None, None
    try:
        name = f"{__name__}_peer_checks"
        spec = importlib.util.spec_from_file_location(name, PEER_CHECKS)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(name, None)
        for required in ("validate_warnings", "rename_note"):
            if not callable(getattr(module, required, None)):
                raise TypeError(f"integration must define {required}")
        result = getattr(module, method)(*args)
        if method == "validate_warnings":
            if not isinstance(result, list) or not all(isinstance(item, str) for item in result):
                raise TypeError("validate_warnings must return a list of strings")
        elif result is not None and not isinstance(result, str):
            raise TypeError("rename_note must return a string or None")
        return result, None
    except Exception as exc:
        return None, f"peer checks configured but unusable: {type(exc).__name__}: {exc}"


def a_validate(reg, a):
    errs, warns = reg.check()
    if a.get("peers", True) is not False:
        extra, problem = peer_call("validate_warnings", reg, norm)
        warns += [problem] if problem else (extra or [])
    return {"ok": not errs, "errors": errs, "warnings": warns}


# --------------------------------------------------------------------------- write actions
PERSON_FIELDS = TABLES["persons"][1:]
PROJECT_FIELDS = tuple(c for c in TABLES["projects"] if c != "id")
REPO_FIELDS = ("owner", "host", "url", "ghq_path", "summary", "status", "review_status")
MEMBER_FIELDS = ("status", "working_relationship", "can_merge", "can_deploy") + tuple(MEMBER_LISTS)


def _set_primary(reg, table, owner_col, owner, row):
    for r in reg.rows(table, **{owner_col: owner}):
        r["is_primary"] = FALSE
    row["is_primary"] = TRUE


def _add_alias(reg, table, owner_col, owner, alias, primary):
    alias = alias.strip()
    row = next((r for r in reg.rows(table, **{owner_col: owner}) if norm(r["alias"]) == norm(alias)), None)
    if row is None:
        row = {owner_col: owner, "alias": alias, "is_primary": FALSE}
        reg.t[table].append(row)
    if primary or not any(flag(r["is_primary"]) for r in reg.rows(table, **{owner_col: owner})):
        _set_primary(reg, table, owner_col, owner, row)
    return row


def a_person_set(reg, a):
    pid = need(a, "id")
    f = fields_of(a, PERSON_FIELDS)
    if "residence_country" in f and f["residence_country"]:
        f["residence_country"] = str(f["residence_country"]).upper()
    if "preferred_language" in f and f["preferred_language"]:
        f["preferred_language"] = str(f["preferred_language"]).lower()
    row = reg.one("persons", id=pid)
    created = row is None
    if created:
        if not f.get("display_name"):
            raise RegistryError("person_set: a new person needs fields.display_name")
        row = {c: "" for c in TABLES["persons"]}
        row.update(id=pid, kind="individual", status="active", review_status="needs_review")
        reg.t["persons"].append(row)
    for k, v in f.items():
        row[k] = cell(v)
    if created:
        _add_alias(reg, "person_aliases", "person_id", pid, row["display_name"], True)
    return {"created": created, "person": person_obj(reg, pid)}


def a_project_set(reg, a):
    pid = need(a, "id")
    f = fields_of(a, PROJECT_FIELDS)
    row = reg.one("projects", id=pid)
    created = row is None
    if created:
        row = {c: "" for c in TABLES["projects"]}
        name = cell(f.get("canonical_name")) or pid
        row.update(id=pid, canonical_name=name, slug=kebab(name), kind="category", status="active",
                   review_status="needs_review")
        reg.t["projects"].append(row)
    old_kind = row["kind"]
    for k, v in f.items():
        row[k] = cell(v)
    if old_kind == "org" and row["kind"] != "org" and reg.rows("projects", organization_id=pid):
        raise RegistryError(f"{pid} is the organization of other projects; it must stay kind=org")
    if created:
        _add_alias(reg, "project_aliases", "project_id", pid, row["canonical_name"], True)
    return {"created": created, "project": project_obj(reg, pid)}


def a_member_set(reg, a):
    project, person = need(a, "project"), need(a, "person")
    reg.project(project)
    reg.person(person)
    f = fields_of(a, MEMBER_FIELDS)
    row = reg.one("memberships", project_id=project, person_id=person)
    created = row is None
    if created:
        row = {c: "" for c in TABLES["memberships"]}
        row.update(project_id=project, person_id=person, status="active", can_merge=FALSE, can_deploy=FALSE)
        reg.t["memberships"].append(row)
    for k, v in f.items():
        if k in MEMBER_LISTS:
            if not isinstance(v, list):
                v = [v] if v not in (None, "") else []
            table, col = MEMBER_LISTS[k]
            reg.delete(table, project_id=project, person_id=person)
            for item in dict.fromkeys(cell(x) for x in v if cell(x)):
                reg.t[table].append({"project_id": project, "person_id": person, col: item})
        elif k in ("can_merge", "can_deploy"):
            row[k] = boolcell(v)
        else:
            row[k] = cell(v)
    return {"created": created, "membership": membership_obj(reg, row)}


def a_member_rm(reg, a):
    project, person = need(a, "project"), need(a, "person")
    if not reg.delete("memberships", project_id=project, person_id=person):
        raise RegistryError(f"no membership {project}/{person}")
    for table, _ in MEMBER_LISTS.values():
        reg.delete(table, project_id=project, person_id=person)
    return {"removed": f"{project}/{person}"}


def a_repo_set(reg, a):
    project, name = need(a, "project"), need(a, "name")
    reg.project(project)
    f = dict(fields_of(a, REPO_FIELDS + ("has_agents_md",)))
    f.pop("has_agents_md", None)  # derived from the clone; accepted for older callers
    row = reg.one("repos", project_id=project, name=name)
    created = row is None
    if created:
        row = {c: "" for c in TABLES["repos"]}
        row.update(project_id=project, name=name, host="github.com", status="declared", review_status="needs_review")
        reg.t["repos"].append(row)
    ghq = f.pop("ghq_path", None)
    for k, v in f.items():
        row[k] = cell(v)
    if created and not row["url"] and row["owner"]:
        row["url"] = f"https://{row['host']}/{row['owner']}/{name}"
    if ghq is not None:
        ghq = cell(ghq)
        default = reg.default_ghq(row)
        same = ghq and default and Path(ghq).expanduser().resolve() == Path(default).resolve()
        row["ghq_path"] = "" if (not ghq or same) else contract_home(Path(ghq).expanduser())
    return {"created": created, "repo": repo_obj(reg, row)}


def a_repo_rm(reg, a):
    project, name = need(a, "project"), need(a, "name")
    if not reg.delete("repos", project_id=project, name=name):
        raise RegistryError(f"no repo {name!r} in {project}")
    return {"removed": f"{project}/{name}"}


def a_link_repo(reg, a):
    """Create <dir_path>/github/<name> -> the ghq clone; never clones. Sets status linked|missing."""
    project, name = need(a, "project"), need(a, "name")
    row = reg.one("repos", project_id=project, name=name)
    if not row:
        raise RegistryError(f"no repo {name!r} in {project}")
    link = reg.link_path(row)
    if not link:
        raise RegistryError(f"project {project} has no directory Projects/{project}; cannot place a symlink")
    ghq = reg.ghq_path(row)
    base = Path(reg.dir_path(project)) / "github"
    if Path(link).parent != base or (ghq and not Path(ghq).is_absolute()):
        raise RegistryError(f"refusing to link {name!r}: the link must sit in {base} and the clone path "
                            "must be absolute")
    if ghq and Path(ghq).exists():
        lp = Path(link)
        if lp.is_symlink() or lp.exists():
            if lp.is_symlink() and lp.resolve() == Path(ghq).resolve():
                note = "symlink already correct"
            else:
                raise RegistryError(f"{lp} already exists and is not the expected symlink")
        else:
            lp.parent.mkdir(parents=True, exist_ok=True)
            lp.symlink_to(ghq)
            note = f"linked {lp} -> {ghq}"
        row["status"] = "linked"
    else:
        row["status"] = "missing"
        note = f"clone not found at {ghq or '(unknown: no owner)'}; declared only (clone it, then link again)"
    return {"action": "link-repo", "project": project, "name": name, "status": row["status"], "note": note}


def a_add(reg, a):
    facet, kind, oid = target(a, PERSON_FACETS, PROJECT_FACETS)
    (reg.person if kind == "person" else reg.project)(oid)
    owner = f"{kind}_id"
    primary = truthy(a.get("primary", False))
    if facet == "alias":
        _add_alias(reg, f"{kind}_aliases", owner, oid, need(a, "value"), primary)
    elif facet == "contact":
        channel, handle = need(a, "channel"), need(a, "value")
        row = next((r for r in reg.rows("person_contacts", person_id=oid)
                    if r["channel"] == channel and norm_handle(r["handle"]) == norm_handle(handle)), None)
        if row is None:
            row = {"person_id": oid, "channel": channel, "handle": handle, "is_primary": FALSE}
            reg.t["person_contacts"].append(row)
        if primary:
            _set_primary(reg, "person_contacts", "person_id", oid, row)
    elif facet in ("language", "nationality"):
        table, col = ("person_languages", "language") if facet == "language" else ("person_nationalities", "country")
        code = need(a, "value")
        code = code.lower() if facet == "language" else code.upper()
        row = reg.one(table, person_id=oid, **{col: code})
        if row is None:
            row = {c: "" for c in TABLES[table]}
            row.update(person_id=oid, is_primary=FALSE, **{col: code})
            reg.t[table].append(row)
        if facet == "language" and a.get("proficiency") is not None:
            row["proficiency"] = cell(a["proficiency"])
        if primary:
            _set_primary(reg, table, "person_id", oid, row)
    elif facet == "note":
        reg.t["person_notes"].append({"person_id": oid, "date": cell(a.get("date")) or date.today().isoformat(),
                                      "text": need(a, "value")})
    elif facet == "link":
        link_kind, url = need(a, "kind"), need(a, "value")
        row = reg.one("project_links", project_id=oid, kind=link_kind, url=url)
        if row is None:
            row = {"project_id": oid, "kind": link_kind, "url": url, "label": ""}
            reg.t["project_links"].append(row)
        if a.get("label") is not None:
            row["label"] = cell(a["label"])
    elif facet == "tag":
        axis, value = need(a, "axis"), need(a, "value")
        if not any(r["axis"] == axis and norm(r["value"]) == norm(value)
                   for r in reg.rows("project_tags", project_id=oid)):
            reg.t["project_tags"].append({"project_id": oid, "axis": axis, "value": value})
    obj = person_obj(reg, oid) if kind == "person" else project_obj(reg, oid)
    return {kind: obj}


def a_remove(reg, a):
    facet, kind, oid = target(a, PERSON_FACETS, PROJECT_FACETS)
    owner = f"{kind}_id"
    value = need(a, "value")
    if facet == "alias":
        n = _drop(reg, f"{kind}_aliases", lambda r: r[owner] == oid and norm(r["alias"]) == norm(value))
    elif facet == "contact":
        channel = a.get("channel")
        n = _drop(reg, "person_contacts", lambda r: r["person_id"] == oid and norm_handle(r["handle"]) == norm_handle(value)
                  and (not channel or r["channel"] == channel))
    elif facet == "language":
        n = _drop(reg, "person_languages", lambda r: r["person_id"] == oid and r["language"] == value.lower())
    elif facet == "nationality":
        n = _drop(reg, "person_nationalities", lambda r: r["person_id"] == oid and r["country"] == value.upper())
    elif facet == "note":
        n = _drop(reg, "person_notes", lambda r: r["person_id"] == oid and r["text"] == value)
    elif facet == "link":
        n = _drop(reg, "project_links", lambda r: r["project_id"] == oid and r["url"] == value
                  and (not a.get("kind") or r["kind"] == a["kind"]))
    else:  # tag
        axis = need(a, "axis")
        n = _drop(reg, "project_tags", lambda r: r["project_id"] == oid and r["axis"] == axis
                  and norm(r["value"]) == norm(value))
    if not n:
        raise RegistryError(f"no {facet} {value!r} on {kind} {oid}")
    return {"removed": n, kind: person_obj(reg, oid) if kind == "person" else project_obj(reg, oid)}


def _drop(reg, table, pred):
    before = len(reg.t[table])
    reg.t[table] = [r for r in reg.t[table] if not pred(r)]
    return before - len(reg.t[table])


def a_rename(reg, a):
    new = need(a, "new_id")
    person, project = a.get("person"), a.get("project")
    if bool(person) == bool(project):
        raise RegistryError("rename: give exactly one of person or project (the current id) and new_id")
    kind, old = ("person", str(person)) if person else ("project", str(project))
    table = f"{kind}s"
    row = reg.person(old) if person else reg.project(old)
    if reg.one(table, id=new):
        raise RegistryError(f"{kind} {new!r} already exists")
    row["id"] = new
    col = f"{kind}_id"
    for t, cols in TABLES.items():
        if col in cols:
            for r in reg.t[t]:
                if r[col] == old:
                    r[col] = new
    note = None
    problem = None
    if person:
        note, problem = peer_call("rename_note", kind, old, new)
    if project:
        for r in reg.t["projects"]:
            if r["organization_id"] == old:
                r["organization_id"] = new
        if (reg.root / "Projects" / old).is_dir():
            note = f"the directory Projects/{old} was not moved; rename it to Projects/{new}"
    out = {"renamed": {"from": old, "to": new}, "note": note}
    if problem:
        out["warnings"] = [problem]
    return out


TEMPLATES = Path(__file__).resolve().parent / "templates"
DIRLESS_KINDS = ("org", "external")


def a_group_create(reg, a):
    """Projects/<id>/{github,docs,data} + a seeded AGENTS.md + the registry row, in that order
    only after the row is known to be valid. Existing directories and AGENTS.md are kept."""
    pid = need(a, "id")
    out = a_project_set(reg, a)
    row = reg.project(pid)
    if row["kind"] in DIRLESS_KINDS:
        raise RegistryError(f"a {row['kind']} project has no Projects/ directory; use project_set")
    errs, _ = reg.check()
    added = [e for e in errs if e not in reg.before_errs]
    if added:
        raise RegistryError("change rejected: " + "; ".join(added))
    base = reg.root / "Projects" / pid
    if base.parent.resolve() != (reg.root / "Projects").resolve():
        raise RegistryError(f"refusing to create {base}")
    made = []
    for sub in ("github", "docs", "data"):
        d = base / sub
        if not d.is_dir():
            d.mkdir(parents=True, exist_ok=True)
            made.append(f"{sub}/")
    agents = base / "AGENTS.md"
    if not agents.exists():
        text = (TEMPLATES / "group.AGENTS.md").read_text(encoding="utf-8").replace("<Group>", pid)
        if row["summary"]:
            text = text.replace("<one-line: what this group is>", row["summary"])
        agents.write_text(text, encoding="utf-8")
        made.append("AGENTS.md")
    return {"created": out["created"], "made": made, "project": project_obj(reg, pid),
            "next": "fill AGENTS.md with real facts; add members with member_set, repos with repo_set + link_repo"}


READS = {"whois": a_whois, "person": a_person, "persons": a_persons, "project": a_project,
         "projects": a_projects, "members": a_members, "repos": a_repos, "search": a_search,
         "review": a_review, "validate": a_validate}
WRITES = {"person_set": a_person_set, "project_set": a_project_set, "member_set": a_member_set,
          "member_rm": a_member_rm, "repo_set": a_repo_set, "repo_rm": a_repo_rm, "link_repo": a_link_repo,
          "group_create": a_group_create,
          "add": a_add, "remove": a_remove, "rename": a_rename}
ACTIONS = tuple(READS) + tuple(WRITES)


def run(args, root=None):
    action = (args or {}).get("action")
    if action in READS:
        reg = Registry.load(root)
        out = READS[action](reg, args)
        if action != "validate" and reg.load_errors:
            out["warnings"] = reg.load_errors
        return out
    if action in WRITES:
        with transaction(root) as reg:
            out = WRITES[action](reg, args)
        errs, _ = Registry.load(root).check()
        if errs:
            out.setdefault("warnings", []).append(f"registry already has {len(errs)} validation error(s); run validate")
        return {"ok": True, **out}
    raise RegistryError("action must be one of " + ", ".join(ACTIONS))


def init(root):
    """Create an empty registry (every CSV with its header). Refuses to touch an existing one."""
    d = data_dir(root)
    if d.exists() and any(d.glob("*.csv")):
        raise RegistryError(f"{d} already holds a registry")
    d.mkdir(parents=True, exist_ok=True)
    reg = Registry(root)
    reg.save(list(TABLES))
    return d
