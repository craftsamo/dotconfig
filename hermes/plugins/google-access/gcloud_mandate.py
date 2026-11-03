"""google-access: gcloud project mandates — the user's standing approval for a few commands in one project.

A mandate is made only on its own approval card and names: one project id, one to five command paths (the
exact leaf paths of the installed SDK's tree, release tracks included: ``run deploy`` and ``beta run
deploy`` are two), up to MAX_FLAGS flags a covered call may use, how many covered commands an hour it allows
(each call counts one), a purpose, and an end at most MAX_DAYS out. A non-read command runs without its card
only when it fits one mandate, and the check is closed: the call names that project and one of the
mandate's paths, the SDK's tree confirms the path, and everything in its arguments is accounted for. Its
flags are long flags the mandate lists (and each is one the tree declares for the command), its positionals
are plain resource ids, and every flag value is a plain token that names no path, URL, other project,
organization or folder; an image (a flag ending in ``image``, ``--pack``) must be in a Google registry path of
the mandate's project. Anything else (an unlisted flag, ``--``, a short flag, a path or ``gs://`` value, an
image from elsewhere) asks on its card. A covered call runs in an empty, private working directory
(``access.gcloud``), so no relative name resolves to anything. Whatever the terms say, these are never covered: a path that ends or undoes something (a delete,
``rm``, a restore, a stop …) or reaches IAM, service accounts, keys, secrets, KMS, billing, projects,
organizations, storage, auth, config, ssh or a tunnel; a command that hands out a credential or writes a
local file; and a flag of the families in ``NEVER_FLAG_WORDS`` (identity, access, network, secrets, local
paths …), which can never be on a mandate's list. A call without a project, or of a command whose path the
SDK's tree could not confirm, is never covered.

State, in the profile home (never the repository; the plugin's guard blocks file and terminal access), kept
by the shared store and ledger (``plugins/_shared/mandate_store.py``, ``plugins/_shared/mandate_ledger.py``)
in the plugin's own state directory, beside the files ``access.py`` keeps there:

  <HERMES_HOME>/google-access/mandates/<id>.json   the terms, MAC'd
  <HERMES_HOME>/google-access/head.json            the ids in force, MAC'd: only the head decides
  <HERMES_HOME>/google-access/uses.jsonl           one MAC'd opening row per mandate, then one per command
  <HERMES_HOME>/google-access/mandates.jsonl       made / revoked history, for the record only

The MAC key is a random key in the Keychain (``GCLOUD_MANDATE_KEY_<PROFILE>``, project hermes, scope
google-access, a scope no profile receives), made with the first mandate. Without a readable key no mandate
is in force and every non-read command asks on its card. ``use`` is the write-time check and the count in one
step, under the store's lock: a command is counted before it runs, whatever becomes of it. The module does
not import ``access.py``: the engine hands it the checked call (``access.GcloudCall``) and ``terms`` the
engine's own validator. Contract: docs/decisions/gcloud-mandates.md.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import threading
import time
from pathlib import Path
from typing import Callable


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


_SHARED = Path(__file__).resolve().parents[1] / "_shared"
cards = _load("hermes_card", _SHARED / "card.py")
mandate_store = _load("hermes_mandate_store", _SHARED / "mandate_store.py")
mandate_ledger = _load("hermes_mandate_ledger", _SHARED / "mandate_ledger.py")

STATE = "google-access"     # the plugin's state directory (access.STATE_DIR)
MAX_DAYS = 7
MAX_COMMANDS = 5
MAX_FLAGS = 20
MAX_PER_HOUR = 10
HOUR = 3600
DAY = mandate_store.DAY
PURPOSE_LIMIT = 200
PURPOSE_CLIPS = (PURPOSE_LIMIT, 120, 60, 30)   # shortened one after the other before a bound is left out
CARD_TTL = 900          # how long a mandate card's record stays valid
HEAD_FILE = "head.json"   # the store's (plugins/_shared/mandate_store.py)
LEDGER_KIND = "gcloud-use"

# A path whose last word is or starts with one of these ends, undoes or moves something (`restore` is also
# `restore-backup`, `undeploy` is `undeploy-model`).
NEVER_ENDINGS = ("delete", "remove", "destroy", "purge", "reset", "cancel", "disable", "undelete", "rm",
                 "restore", "stop", "suspend", "undeploy", "abandon", "revoke", "replace")
# Words that reach identity, access, secrets, money, the project itself, storage or a way in. A word of a
# path counts when it is one of these or holds one as a dash-delimited run (`iam` is also `get-iam-policy`
# and `set-iam-policy`; `keys` is `api-keys`; `iap` is `start-iap-tunnel`; `metadata` is `add-metadata`).
# `storage` is the whole group: it moves local and cross-project data by positionals. `builds` runs
# arbitrary build steps.
NEVER_WORDS = ("builds", "iam", "service-account", "service-accounts", "keys", "secrets", "kms", "billing",
               "organizations", "folders", "projects", "resource-manager", "auth", "config", "ssh", "scp", "iap",
               "tunnel", "proxy", "port-forward", "connect", "access-approval", "org-policies", "identity", "pam",
               "access-context-manager", "firewall-rules", "access-config", "metadata", "password", "scc",
               "storage")
# Flags that change who may reach a service, which identity it runs as, its secrets, its network, what it
# mounts or where data goes, matched on the flag's dash-delimited words once a leading verb or `no-` is
# stripped (`--no-iap` and `--clear-network` are `iap` and `network`; `--delete-*` holds `delete`). They can
# never be on a mandate's list (`project` is `--image-project`, `--source-project`, `--host-project` …).
# `unauthenticated`, `bucket`, `volume(s)` and `subnetwork` go beyond what a review named: a public
# service, a staging or trigger bucket, a mounted secret or bucket, a subnet.
NEVER_FLAG_WORDS = ("service-account", "service-accounts", "ingress", "egress", "network", "networks", "vpc",
                    "subnet", "subnetwork", "iap", "invoker", "iam", "member", "role", "roles", "acl", "pap",
                    "public", "authorized-networks", "kms", "key", "keys", "secret", "secrets", "breakglass",
                    "binary-authorization", "security-level", "scopes", "metadata", "ssl", "assign-ip", "address",
                    "source-ranges", "audiences", "cloudsql", "workload-pool", "legacy-authorization", "identity",
                    "organization", "folder", "billing-project", "impersonate", "account", "configuration",
                    "delete", "unauthenticated", "bucket", "volume", "volumes", "project", "projects", "namespace",
                    "password")
NEVER_FLAG_VERBS = ("no", "clear", "set", "update", "add", "remove")   # stripped from the front of a flag
# A flag whose last word names a local path, and the one flag that names the source to upload.
NEVER_FLAG_ENDINGS = ("file", "dir", "directory", "path")
NEVER_FLAG_SOURCE = "--source"
# What a covered call may carry. Flags are long flags the mandate lists; a flag value and a positional are
# plain tokens, so none names a local path, a URL or another project, organization or folder.
FLAG_NAME = re.compile(r"^--[a-z0-9][a-z0-9-]*$")
POSITIONAL = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")
FLAG_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._,:=@/-]{0,299}$")   # not starting with /, ~ or .
VALUE_NEVER = ("gs://", "://", "projects/", "organizations/", "folders/", "..")
# A container image must name a registry path of the mandate's project, exactly: `gcr.io/<project>/`,
# `<us|eu|asia>.gcr.io/<project>/` or `<region>-docker.pkg.dev/<project>/`, with no port and no trailing dot
# (case does not matter). A flag whose last word is `image` (or last two `image-url`) must hold one, so
# `docker.io`, `ghcr.io` and a bare `nginx` ask; so must any other value that starts like a Google registry.
IMAGE_REGISTRY = re.compile(r"^(?:gcr\.io|(?:us|eu|asia)\.gcr\.io|[a-z0-9-]+-docker\.pkg\.dev)/([^/]+)/",
                            re.IGNORECASE)
REGISTRY_HOST = re.compile(r"^(?:[a-z0-9-]+\.)?gcr\.io(?![a-z0-9-])|^[a-z0-9-]+-docker\.pkg\.dev(?![a-z0-9-])",
                           re.IGNORECASE)
IMAGE_FLAG_ENDINGS = (("image",), ("image", "url"))   # the last words of a flag that names an image
PACK_FLAG = "--pack"                                  # `image=` and `builder=` name images
PACK_IMAGE_KEYS = ("image", "builder")

EFFECT = (cards.DANGER, "These commands skip the card in this project")
NEVER = ("deletes and stops, IAM and service accounts, secrets and keys, billing, projects and organizations, "
         "storage, ssh and tunnels, access, network or local-path flags, any other flag, path or URL")
NO_KEY = "no mandate key is readable: nothing is in force"
NO_TREE = "the command path could not be checked against the installed gcloud's command tree"
LEDGER_USED_UP = "its command count cannot be read (the ledger is missing or was changed); it counts as used up"


class MandateError(ValueError):
    """The terms are not acceptable, or the mandate could not be kept."""


STORE = mandate_store.Store(state=STATE, key_prefix="GCLOUD_MANDATE_KEY_", scope="google-access",
                            mac_kind="gcloud-mandate", key_note="google-access gcloud mandate MAC key",
                            error=MandateError, max_days=MAX_DAYS)

# The hour's count of a ledger that cannot be vouched for: it equals MAX_PER_HOUR, so every mandate reads as
# used up, and ``_hourly`` can still tell it from a real count that reached the same number.
USED_UP = mandate_ledger.UsedUp(MAX_PER_HOUR)

# The engine's validator of one gcloud call: ``access.gcloud_call``.
Judge = Callable[[dict], object]


# --- what is never covered ------------------------------------------------------------------------

def _holds(word: str, name: str) -> bool:
    """Whether ``word`` is ``name`` or holds it as a run of dash-delimited parts."""
    parts, wanted = word.split("-"), name.split("-")
    return any(parts[i:i + len(wanted)] == wanted for i in range(len(parts) - len(wanted) + 1))


def _never_path(path) -> str | None:
    command = "gcloud " + " ".join(path)
    if path[-1].startswith(NEVER_ENDINGS):
        return f"{command} ends or undoes something ({path[-1]}); it always asks on a card"
    for word in path:
        for name in NEVER_WORDS:
            if _holds(word, name):
                return f"{command} reaches {name}; it always asks on a card"
    return None


def never_flag(flag: str) -> str | None:
    """Why no mandate may list ``flag`` (a long flag, ``--name``), or None."""
    words = flag[len("--"):].split("-")
    while len(words) > 1 and words[0] in NEVER_FLAG_VERBS:
        words = words[1:]
    if flag == NEVER_FLAG_SOURCE or words[-1] in NEVER_FLAG_ENDINGS:
        return f"{flag} names a local path or source; it always asks on a card"
    core = "-".join(words)
    for family in NEVER_FLAG_WORDS:
        if _holds(core, family):
            return f"{flag} changes access, identity, secrets, the network or data ({family}); it always asks on a card"
    return None


def never(call) -> str | None:
    """Why the call is one no mandate covers, whatever its terms say, or None. ``call`` is the engine's
    ``access.GcloudCall``: its command path as the SDK's tree names it, whether the path is a sensitive one
    or a flag writes a local file. The flags themselves are judged one by one (``never_flag``)."""
    if not call.resolved:
        return NO_TREE
    if call.sensitive:
        return f"gcloud {' '.join(call.path)} hands out a credential or key material; it always asks on a card"
    if call.writes_file:
        return "a flag that writes a local file always asks on a card"
    return _never_path(call.path)


# --- terms ----------------------------------------------------------------------------------------

def _whole(value, name: str, low: int, high: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise MandateError(f"{name} is a whole number from {low} to {high}")
    return value


def terms(project, commands, flags, per_hour, days, purpose, judge: Judge, now: float | None = None) -> dict:
    """The terms of a new mandate, checked. ``commands`` are command paths as words; ``judge({"command":
    words, "project": project, "args": [...]})`` is the engine's validator (``access.gcloud_call``), which
    refuses what the tool would reject and answers the call it would run: each path must be a command of the
    installed SDK's tree that is not a read and not one that is never covered. ``flags`` (none when omitted)
    are the long flags a covered call may use: none in a never-covered family or writing a local file, and
    each one the tree declares for at least one of the paths. The end is fixed now, when the card is drawn,
    so what is stored ends when the card said."""
    if not isinstance(project, str) or not project.strip():
        raise MandateError("project is the one project id the mandate covers (a string)")
    project = project.strip()
    if (not isinstance(commands, (list, tuple)) or not 1 <= len(commands) <= MAX_COMMANDS
            or any(not isinstance(words, (list, tuple)) or not words for words in commands)):
        raise MandateError(f"commands is a list of one to {MAX_COMMANDS} command paths, each a list of words, "
                           "e.g. [\"run\", \"deploy\"]")
    flags = [] if flags is None else flags
    if (not isinstance(flags, (list, tuple)) or len(flags) > MAX_FLAGS
            or any(not isinstance(flag, str) or not FLAG_NAME.fullmatch(flag) for flag in flags)):
        raise MandateError(f"flags is a list of at most {MAX_FLAGS} long flags like --region (lowercase, with "
                           "the leading --); none when the call needs none")
    per_hour = _whole(per_hour, "per_hour", 1, MAX_PER_HOUR)
    days = _whole(days, "days", 1, MAX_DAYS)
    purpose = " ".join(str(purpose or "").split())
    if not purpose:
        raise MandateError("purpose says what the mandate is for (one line)")
    if len(purpose) > PURPOSE_LIMIT:
        raise MandateError(f"purpose is at most {PURPOSE_LIMIT} characters")
    paths, judged = [], []
    for words in commands:
        call = judge({"command": list(words), "project": project})
        shown = "gcloud " + " ".join(call.path if call.resolved else words)
        if not call.resolved:
            raise MandateError(f"{shown}: {NO_TREE}")
        if call.read_only:
            raise MandateError(f"{shown} is a read; it needs no mandate")
        why = never(call)
        if why:
            raise MandateError(why)
        if list(call.path) in paths:
            raise MandateError(f"{shown} is named twice")
        paths.append(list(call.path))
        judged.append(call)
    for n, flag in enumerate(flags):
        why = never_flag(flag)
        if why:
            raise MandateError(why)
        if flag in flags[:n]:
            raise MandateError(f"{flag} is named twice")
        if judge({"command": paths[0], "project": project, "args": [flag]}).writes_file:
            raise MandateError(f"{flag} writes a local file; it always asks on a card")
        if not any(call.kind(flag) for call in judged):
            raise MandateError(f"{flag} is not a flag of any of the named commands in the installed gcloud")
    now = time.time() if now is None else now
    return {"project": project, "commands": paths, "flags": list(flags), "per_hour": per_hour, "days": days,
            "expires": int(now) + days * DAY, "purpose": purpose}


def same_terms(a: dict, b: dict) -> bool:
    """Whether two readings of a create call agree on everything but the end (fixed at the card)."""
    return {k: v for k, v in a.items() if k != "expires"} == {k: v for k, v in b.items() if k != "expires"}


def card(t: dict) -> str:
    """The shared card shape (plugins/_shared/card.py) with every bound of the mandate on it: the rule every
    mandate shares goes last and is dropped first, the purpose shrinks until it fits, and a mandate whose
    card still does not fit is refused."""
    end = time.strftime("%Y-%m-%d %H:%M", time.localtime(t["expires"]))
    for purpose_clip in PURPOSE_CLIPS:
        facts = [("Project", t["project"])]
        facts += [("Command", "gcloud " + " ".join(path)) for path in t["commands"]]
        facts += [("Flags", ", ".join(t["flags"]) or "none"), ("Up to", f"{t['per_hour']} commands an hour"),
                  ("Until", f"{end} ({t['days']} day{'s' if t['days'] != 1 else ''})"),
                  ("Purpose", cards.line(t["purpose"], purpose_clip))]
        try:
            return cards.compose("gcloud", "Project mandate", EFFECT, facts, context=[("Never covered", NEVER)])
        except cards.CardError:
            continue
    raise MandateError("the mandate's card cannot show all its bounds; name fewer commands or flags (a Discord "
                       "chat shows a shorter card than Telegram)")


# --- the card a create call was shown -------------------------------------------------------------
# The hook records the terms its card showed, per exact call; the handler takes that record once. A
# create call whose card was never shown (or shown too long ago) makes nothing.

_SHOWN: dict[str, tuple[float, dict]] = {}
_SHOWN_LOCK = threading.Lock()


def _call_key(args: dict, call_id: str) -> str:
    return hashlib.sha256(json.dumps([call_id or "", args], sort_keys=True, ensure_ascii=False,
                                     default=str).encode("utf-8")).hexdigest()


def note_card(args: dict, call_id: str, t: dict) -> None:
    now = time.monotonic()
    with _SHOWN_LOCK:
        for old in [k for k, (at, _) in _SHOWN.items() if now - at > CARD_TTL]:
            del _SHOWN[old]
        _SHOWN[_call_key(args, call_id)] = (now, t)


def take_card(args: dict, call_id: str) -> dict | None:
    """The terms the card of this very call showed, consumed; None without one."""
    with _SHOWN_LOCK:
        found = _SHOWN.pop(_call_key(args, call_id), None)
    if not found or time.monotonic() - found[0] > CARD_TTL:
        return None
    return found[1]


# --- what is in force -----------------------------------------------------------------------------

def active(home, now: float | None = None) -> list[dict]:
    """The mandates in force: in the authenticated head, authenticated themselves, not ended. Until a first
    mandate has been made there is no head, and the Keychain is not asked."""
    if not (mandate_store.state_dir(STORE, home) / HEAD_FILE).is_file():
        return []
    return mandate_store.active(STORE, home, now)


def create(home, t: dict) -> dict:
    """Make the mandate the card showed; returns its ``summary``. Its opening row goes into the ledger right
    after: a mandate whose opening row is missing counts as used up, so one that cannot be anchored is
    revoked and nothing is made."""
    fields = {k: t[k] for k in ("project", "commands", "flags", "per_hour", "purpose")}
    body = mandate_store.create(STORE, home, fields, t["expires"])
    try:
        with mandate_store.locked(STORE, home):
            secret = mandate_store.key(STORE, home)
            if secret is None:
                raise MandateError(NO_KEY)
            mandate_ledger.anchor(STORE, home, secret, LEDGER_KIND, body["id"], body["created"])
    except (OSError, MandateError) as exc:
        try:
            mandate_store.revoke(STORE, home, body["id"])
            ended = "it was revoked"
        except (OSError, MandateError) as revoke_exc:
            ended = f"it could not be revoked ({revoke_exc}); revoke {body['id']}"
        raise MandateError(f"the mandate could not be recorded in its ledger ({exc}); nothing was made, "
                           f"{ended}") from exc
    return summary(body)


def revoke(home, mandate_id: str) -> dict:
    """Take a mandate out of force at once; needs no card."""
    return mandate_store.revoke(STORE, home, mandate_id)


def summary(body: dict) -> dict:
    return {"id": body["id"], "until": time.strftime("%Y-%m-%d %H:%M", time.localtime(body["expires"])),
            "project": body["project"], "commands": [" ".join(path) for path in body["commands"]],
            "flags": body.get("flags", []), "per_hour": body["per_hour"], "purpose": body["purpose"]}


# --- does a command fit ---------------------------------------------------------------------------

def _is_image_flag(flag: str) -> bool:
    words = tuple(flag[len("--"):].split("-"))
    return any(words[-len(ending):] == ending for ending in IMAGE_FLAG_ENDINGS)


def _in_project_registry(image: str, project: str) -> bool:
    found = IMAGE_REGISTRY.match(image)
    return bool(found) and found.group(1).lower() == project.lower()


def _pack_why(flag: str, value: str, project: str) -> str | None:
    """Why a `--pack` value (`image=…,builder=…,env=…`) does not name its images in the project, or None."""
    named = [(key.lower(), image) for key, _, image in (item.partition("=") for item in value.split(","))
             if key.lower() in PACK_IMAGE_KEYS]
    if not any(key == "image" for key, _ in named) or not all(_in_project_registry(image, project)
                                                              for _, image in named):
        return f"the image and builder of {flag} are not both in a registry of the mandate's project"
    return None


def _value_why(flag: str, value: str, project: str) -> str | None:
    """Why a flag's value is not a plain token of the mandate's project, or None."""
    if not FLAG_VALUE.fullmatch(value) or any(part in value for part in VALUE_NEVER):
        return f"the value of {flag} is not a plain token (no path, URL, project, organization or folder)"
    if flag == PACK_FLAG:
        return _pack_why(flag, value, project)
    if (_is_image_flag(flag) or REGISTRY_HOST.match(value)) and not _in_project_registry(value, project):
        return f"the value of {flag} is not an image in a registry of the mandate's project"
    return None


def _arguments_why(m: dict, call) -> str | None:
    """Why the call's arguments are not all accounted for: the closed part of the check. Only long flags the
    mandate lists (and none of the never-covered families), each with a plain value, and positionals that are
    plain resource ids."""
    if call.unparsed:
        return call.unparsed
    listed = m.get("flags") or []
    for flag, value in call.flags:
        why = never_flag(flag)
        if why:
            return why
        if flag not in listed:
            return f"{flag} is not one of the mandate's flags"
        if value is not None:
            why = _value_why(flag, value, m["project"])
            if why:
                return why
    for positional in call.positionals:
        if not POSITIONAL.fullmatch(positional):
            return f"{positional!r} is not a plain resource id"
    return None


def fits(m: dict, call) -> str | None:
    """Why the gcloud call (``access.GcloudCall``) does not fit mandate ``m``, or None when it does."""
    why = never(call)
    if why:
        return why
    if not call.project:
        return "a call without a project is never covered; name the mandate's project"
    if call.project != m["project"]:
        return f"{call.project} is not the mandate's project"
    if list(call.path) not in m["commands"]:
        return f"gcloud {' '.join(call.path)} is not one of the mandate's commands"
    return _arguments_why(m, call)


def _hourly(m: dict, used: int) -> str | None:
    """Why one more command does not fit the hour that already holds ``used``, or None."""
    if isinstance(used, mandate_ledger.UsedUp):
        return LEDGER_USED_UP
    if used + 1 > m["per_hour"]:
        return f"{used} commands in the last hour; the mandate allows {m['per_hour']} an hour"
    return None


def covering(home, call, now: float | None = None) -> tuple[str | None, list[str]]:
    """(the id of a mandate in force the call fits and whose hour has room for it, or None; why each mandate
    in force did not). Until a mandate has ever been made there is no head, and the Keychain is not asked."""
    now = time.time() if now is None else now
    if not (mandate_store.state_dir(STORE, home) / HEAD_FILE).is_file():
        return None, []
    secret = mandate_store.key(STORE, home)
    if secret is None:
        return None, []
    misses = []
    for m in mandate_store.active(STORE, home, now, key_of=lambda _home: secret):
        used = mandate_ledger.count(STORE, home, secret, LEDGER_KIND, m["id"], now, HOUR, USED_UP)
        why = fits(m, call) or _hourly(m, used)
        if why is None:
            return m["id"], misses
        misses.append(f"{m['id']}: {why}")
    return None, misses


def use(home, mandate_id: str, call, now: float | None = None) -> str | None:
    """At the write: why the call no longer fits ``mandate_id`` (nothing is counted), or None after the
    command has been counted (one ledger row). The mandate is read again, the hour's count taken and the row
    appended under the store's lock, which revoking and every other caller share: the last slot of an hour
    goes to one."""
    now = time.time() if now is None else now
    try:
        with mandate_store.locked(STORE, home):
            secret = mandate_store.key(STORE, home)
            if secret is None:
                return NO_KEY
            m = next((m for m in mandate_store.active(STORE, home, now, key_of=lambda _home: secret)
                      if m["id"] == mandate_id), None)
            if m is None:
                return f"mandate {mandate_id} is no longer in force"
            return mandate_ledger.take(STORE, home, secret, LEDGER_KIND, mandate_id, now, HOUR, USED_UP,
                                       lambda used: fits(m, call) or _hourly(m, used))
    except (OSError, MandateError) as exc:
        return f"the command could not be counted: {exc}"
