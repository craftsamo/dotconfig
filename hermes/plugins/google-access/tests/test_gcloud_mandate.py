"""gcloud project mandates: the terms, the card, making and ending one, and the commands that run on one
instead of a card; a carded command runs only as its card showed."""

import importlib.util
import json
import os
import re
import stat
import subprocess
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("google_access_gcloud_mandate_plugin_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
access = plugin.access
mandate = plugin.mandate

PROJECT = "my-proj"
HOUR = 3600


ROOT_FLAGS = {"--format": "value", "--quiet": "bool", "--project": "dynamic", "--account": "value",
              "--verbosity": ["debug", "info"]}
# What every stub command declares: flags a mandate may list, and flags of the never-covered families.
LEAF_FLAGS = {"--image": "value", "--region": "value", "--memory": "value", "--tag": "value",
              "--set-env-vars": "value", "--cpu-throttling": "bool", "--no-traffic": "bool", "--async": "bool",
              "--ingress": "value", "--ingress-settings": "value", "--service-account": "value",
              "--run-service-account": "value", "--build-service-account": "value", "--security-level": "value",
              "--iap": "bool", "--breakglass": "value", "--clear-network": "bool", "--key": "value",
              "--predefined-acl": "value", "--pap": "value", "--scopes": "value", "--metadata": "value",
              "--assign-ip": "bool", "--require-ssl": "bool", "--env-vars-file": "value", "--source": "value",
              "--delete-labels": "value", "--organization": "value", "--folder": "value", "--ignore-file": "value",
              "--output-dir": "value", "--allow-unauthenticated": "bool", "--set-secrets": "value",
              "--vpc-connector": "value", "--member": "value", "--role": "value", "--network": "value",
              "--output-file": "value", "--destination": "value", "--add-volume": "value",
              "--stage-bucket": "value", "--subnetwork": "value", "--invoker-iam-check": "bool",
              "--image-url": "value", "--base-image": "value", "--pack": "value"}
# The flags of LEAF_FLAGS that no never-covered family holds: the ones a mandate may list.
LISTABLE = ["--image", "--region", "--memory", "--tag", "--set-env-vars", "--cpu-throttling", "--no-traffic",
            "--async"]


def tree(spec):
    """{"a": {"b": None}} -> gcloud's completion-tree shape; None marks a command (leaf)."""
    return {"commands": {name: tree_node(child) for name, child in spec.items()}, "flags": ROOT_FLAGS}


def tree_node(child):
    if child:
        return {"commands": {name: tree_node(grand) for name, grand in child.items()}, "flags": {}}
    return {"commands": {}, "flags": dict(LEAF_FLAGS)}


TREE = tree({
    "run": {"deploy": None, "services": {"update": None, "describe": None, "list": None, "delete": None,
                                         "undelete": None, "add-iam-policy-binding": None,
                                         "set-iam-policy": None, "proxy": None, "replace": None},
            "jobs": {"list": None, "deploy": None, "replace": None}},
    "functions": {"deploy": None, "delete": None},
    "app": {"deploy": None},
    "beta": {"run": {"deploy": None}},
    "alpha": {"run": {"deploy": None}},
    "projects": {"list": None, "create": None, "add-iam-policy-binding": None},
    "compute": {"ssh": None, "scp": None, "start-iap-tunnel": None, "firewall-rules": {"create": None},
                "instances": {"list": None, "create": None, "remove-metadata": None, "reset": None, "stop": None,
                              "suspend": None, "set-service-account": None, "add-access-config": None,
                              "add-metadata": None},
                "instance-groups": {"managed": {"abandon-instances": None}}},
    "firestore": {"databases": {"undelete": None}},
    "tasks": {"queues": {"purge": None}},
    "builds": {"submit": None, "cancel": None},
    "services": {"enable": None, "disable": None, "api-keys": {"create": None}},
    "iam": {"service-accounts": {"create": None}, "roles": {"create": None}},
    "secrets": {"create": None, "versions": {"access": None}},
    "kms": {"keys": {"create": None}},
    "billing": {"budgets": {"create": None}},
    "organizations": {"add-iam-policy-binding": None},
    "folders": {"create": None},
    "resource-manager": {"tags": {"create": None}},
    "sql": {"connect": None, "backups": {"restore": None}, "instances": {"restore-backup": None},
            "users": {"set-password": None}},
    "workstations": {"port-forward": None, "start-tcp-tunnel": None},
    "access-approval": {"settings": {"update": None}},
    "org-policies": {"set-policy": None},
    "iap": {"settings": {"set": None}},
    "container": {"clusters": {"get-credentials": None}},
    "storage": {"rm": None, "cp": None},
    "ai": {"endpoints": {"undeploy-model": None}},
    "privateca": {"certificates": {"revoke": None}},
    "identity": {"groups": {"create": None}},
    "pam": {"entitlements": {"create": None}},
    "access-context-manager": {"policies": {"create": None}},
    "scc": {"notifications": {"create": None}},
    "auth": {"list": None, "login": None},
    "config": {"set": None},
})


def fake_cli(path, keyfile):
    """A secret CLI over one key file: ``get`` prints it, ``show`` says it exists, ``set --stdin`` stores it."""
    path.write_text(f"#!/bin/sh\n[ \"$1\" = get ] && [ -f {keyfile} ] && cat {keyfile} && exit 0\n"
                    f"[ \"$1\" = show ] && [ -f {keyfile} ] && exit 0\n"
                    f"[ \"$1\" = set ] && [ ! -f {keyfile} ] && cat > {keyfile} && exit 0\nexit 1\n")
    path.chmod(0o755)
    return path


class Ctx:
    def __init__(self, profile):
        self.profile_name = profile
        self.tools = {}
        self.hooks = []
        self.skills = {}

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = path

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


class Rig:
    """The Assistant's tools over a fake gcloud (every run kept), a fake Keychain and a profile home of their own."""

    def __init__(self, monkeypatch, tmp_path):
        self.keyfile = tmp_path / "keyfile"
        self.home = tmp_path / "profile"
        access.gcloud_config_dir(self.home).mkdir(parents=True)
        self.ran = []
        self.cwds = []   # per run: None, or (the directory, what it held, its mode) as the command saw it
        self.exit_code = 0
        self.nobody = None   # why nobody can answer a card, or None
        self.monkeypatch = monkeypatch
        self.calls = 0
        monkeypatch.setattr(mandate.mandate_store, "SECRET", fake_cli(tmp_path / "secret", self.keyfile))
        monkeypatch.setattr(access, "_command_tree", lambda: TREE)
        monkeypatch.setattr(access, "_gcloud_binary", lambda: "/bin/gcloud")
        monkeypatch.setattr(access, "subprocess", SimpleNamespace(
            run=self.run, DEVNULL=subprocess.DEVNULL, TimeoutExpired=subprocess.TimeoutExpired))
        monkeypatch.setattr(mandate.cards, "roomy", lambda: False)
        monkeypatch.setattr(plugin, "_home", lambda: self.home)
        monkeypatch.setattr(plugin, "_card_home", lambda: self.home)
        monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
        monkeypatch.setattr(plugin.human_gate, "no_human", lambda: self.nobody)
        access._GCLOUD_APPROVED.clear()
        mandate._SHOWN.clear()
        ctx = Ctx("assistant")
        plugin.register(ctx)
        self.handlers = {name: tool["handler"] for name, tool in ctx.tools.items()}
        self.gate = ctx.hooks[0][1]

    def run(self, argv, **kwargs):
        self.ran.append(argv)
        cwd = kwargs.get("cwd")
        self.cwds.append(cwd and (cwd, os.listdir(cwd), stat.S_IMODE(os.stat(cwd).st_mode)))
        if self.exit_code == "timeout":
            raise subprocess.TimeoutExpired(argv, 1)
        return SimpleNamespace(returncode=self.exit_code, stdout="ok", stderr="")

    def call(self, tool, args, approve=True):
        """The hook, then (unless it blocked or the card was denied) the handler: (directive, result)."""
        self.calls += 1
        call_id = f"call-{self.calls}"
        self.monkeypatch.setattr(plugin, "_call_id", lambda: call_id)
        directive = self.gate(tool_name=tool, args=args, tool_call_id=call_id)
        if directive and (directive["action"] == "block" or not approve):
            return directive, None
        return directive, json.loads(self.handlers[tool](args))

    def gcloud(self, args):
        return self.call("gcloud", args)

    def make(self, **over):
        directive, result = self.call("gcloud_mandate", create(**over))
        assert directive["action"] == "approve" and result["ok"] is True, (directive, result)
        return result["mandate"]

    def listed(self):
        return json.loads(self.handlers["gcloud_mandate"]({"action": "list"}))["mandates"]

    def used(self, mandate_id, now=None):
        secret = mandate.mandate_store.key(mandate.STORE, self.home)
        return mandate.mandate_ledger.count(mandate.STORE, self.home, secret, mandate.LEDGER_KIND, mandate_id,
                                            now or time.time(), HOUR, mandate.USED_UP)


@pytest.fixture
def rig(monkeypatch, tmp_path):
    return Rig(monkeypatch, tmp_path)


def create(**over):
    return {"action": "create", "project": PROJECT, "commands": [["run", "deploy"], ["run", "services", "update"]],
            "flags": LISTED, "per_hour": 5, "days": 3, "purpose": "Ship the staging service", **over}


def deploy(*extra, project=PROJECT, command=("run", "deploy")):
    args = {"command": list(command), "args": ["svc", "--image=gcr.io/my-proj/app", "--region=asia-northeast1",
                                               *extra]}
    return {**args, "project": project} if project else args


def judge(words, project=PROJECT):
    return access.gcloud_call({"command": words, "project": project})


LISTED = ["--image", "--region", "--memory", "--set-env-vars", "--format", "--no-cpu-throttling"]
GOOD = dict(project=PROJECT, commands=[["run", "deploy"], ["run", "services", "update"]], flags=LISTED[:2],
            per_hour=5, days=3, purpose="Ship the staging service", judge=access.gcloud_call)


@pytest.fixture(autouse=True)
def fake_tree(monkeypatch):
    monkeypatch.setattr(access, "_command_tree", lambda: TREE)


# --- the terms ------------------------------------------------------------------------------------

def test_terms_are_checked_and_fixed_at_the_card():
    t = mandate.terms(**{**GOOD, "purpose": "  Ship\n the   service "}, now=1000)
    assert t["project"] == PROJECT and t["purpose"] == "Ship the service"
    assert t["commands"] == [["run", "deploy"], ["run", "services", "update"]] and t["flags"] == LISTED[:2]
    assert t["expires"] == 1000 + 3 * mandate.DAY
    assert mandate.same_terms(t, {**t, "expires": 1}) and not mandate.same_terms(t, {**t, "per_hour": 6})
    assert not mandate.same_terms(t, {**t, "flags": ["--region", "--image"]})
    assert not mandate.same_terms(t, {**t, "flags": []})


def test_no_flags_is_a_mandate_of_flagless_calls_and_omitting_them_means_none():
    assert mandate.terms(**{**GOOD, "flags": []})["flags"] == []
    assert mandate.terms(**{**GOOD, "flags": None})["flags"] == []


@pytest.mark.parametrize("over, message", [
    ({"per_hour": 0}, "per_hour is a whole number from 1 to 10"),
    ({"per_hour": 11}, "per_hour is a whole number from 1 to 10"),
    ({"per_hour": True}, "per_hour"),
    ({"per_hour": "5"}, "per_hour"),
    ({"days": 0}, "days is a whole number from 1 to 7"),
    ({"days": 8}, "days is a whole number from 1 to 7"),
    ({"days": True}, "days"),
    ({"days": 1.5}, "days"),
    ({"project": None}, "project is the one project id"),
    ({"project": " "}, "project is the one project id"),
    ({"project": ["a-proj", "b-proj"]}, "project is the one project id"),
    ({"commands": []}, "one to 5 command paths"),
    ({"commands": [["run", "deploy"]] * 6}, "one to 5 command paths"),
    ({"commands": "run deploy"}, "one to 5 command paths"),
    ({"commands": ["run deploy"]}, "one to 5 command paths"),
    ({"commands": [[]]}, "one to 5 command paths"),
    ({"flags": "--image"}, "flags is a list of at most 20"),
    ({"flags": [3]}, "flags is a list of at most 20"),
    ({"flags": ["image"]}, "flags is a list of at most 20"),
    ({"flags": ["--Image"]}, "flags is a list of at most 20"),
    ({"flags": ["-q"]}, "flags is a list of at most 20"),
    ({"flags": ["--"]}, "flags is a list of at most 20"),
    ({"flags": ["--image=x"]}, "flags is a list of at most 20"),
    ({"flags": [f"--f{n}" for n in range(21)]}, "flags is a list of at most 20"),
    ({"flags": ["--image", "--image"]}, "--image is named twice"),
    ({"flags": ["--nope"]}, "--nope is not a flag of any of the named commands"),
    ({"flags": ["--no-memory"]}, "--no-memory is not a flag of any of the named commands"),
    ({"purpose": ""}, "purpose says what"),
    ({"purpose": "x" * 201}, "at most 200"),
])
def test_terms_refuse_what_is_out_of_bounds(over, message):
    with pytest.raises(mandate.MandateError, match=re.escape(message)):
        mandate.terms(**{**GOOD, **over})


def test_five_commands_and_twenty_flags_are_the_ceilings():
    five = [["run", "deploy"], ["run", "services", "update"], ["functions", "deploy"], ["app", "deploy"],
            ["run", "jobs", "deploy"]]
    assert mandate.terms(**{**GOOD, "commands": five})["commands"] == five
    assert mandate.MAX_FLAGS == 20
    assert len(mandate.terms(**{**GOOD, "flags": LISTABLE})["flags"]) == len(LISTABLE)


def test_a_negated_flag_is_listed_only_as_that_exact_form_and_only_of_a_bool_flag():
    assert mandate.terms(**{**GOOD, "flags": ["--no-cpu-throttling"]})["flags"] == ["--no-cpu-throttling"]
    assert mandate.terms(**{**GOOD, "flags": ["--no-traffic"]})["flags"] == ["--no-traffic"]   # the tree lists it
    with pytest.raises(mandate.MandateError, match="not a flag of any"):
        mandate.terms(**{**GOOD, "flags": ["--no-memory"]})   # --memory takes a value


@pytest.mark.parametrize("over, error, message", [
    ({"commands": [["run", "deplyo"]]}, access.AccessError, "not a gcloud command path"),
    ({"commands": [["run", "services"]]}, access.AccessError, "command group"),
    ({"commands": [["run", "deploy", "--image=x"]]}, access.AccessError, "lowercase words"),
    ({"commands": [["auth", "login"]]}, access.AccessError, "gaccess"),
    ({"commands": [[3]]}, access.AccessError, "lowercase words"),
    ({"project": "x; rm -rf /"}, access.AccessError, "not a project id"),
    ({"commands": [["run", "services", "list"]]}, mandate.MandateError, "is a read; it needs no mandate"),
    ({"commands": [["run", "deploy"], ["run", "deploy"]]}, mandate.MandateError, "named twice"),
])
def test_a_path_the_tool_would_reject_or_that_needs_no_mandate_is_refused(over, error, message):
    with pytest.raises(error, match=re.escape(message)):
        mandate.terms(**{**GOOD, **over})


def test_without_the_sdk_tree_no_mandate_is_made(monkeypatch):
    monkeypatch.setattr(access, "_command_tree", lambda: None)
    with pytest.raises(mandate.MandateError, match="could not be checked"):
        mandate.terms(**GOOD)


NEVER_PATHS = [   # the path, and the part of the reason that names the rule it falls under
    pytest.param(["run", "services", "delete"], "(delete)", id="delete"),
    pytest.param(["firestore", "databases", "undelete"], "(undelete)", id="undelete"),
    pytest.param(["compute", "instances", "remove-metadata"], "(remove-metadata)", id="remove"),
    pytest.param(["tasks", "queues", "purge"], "(purge)", id="purge"),
    pytest.param(["compute", "instances", "reset"], "(reset)", id="reset"),
    pytest.param(["builds", "cancel"], "(cancel)", id="cancel"),
    pytest.param(["services", "disable"], "(disable)", id="disable"),
    pytest.param(["storage", "rm"], "(rm)", id="storage-rm"),
    pytest.param(["run", "services", "replace"], "(replace)", id="services-replace"),
    pytest.param(["run", "jobs", "replace"], "(replace)", id="jobs-replace"),
    pytest.param(["builds", "submit"], "reaches builds", id="builds-submit"),
    pytest.param(["sql", "backups", "restore"], "(restore)", id="restore"),
    pytest.param(["sql", "instances", "restore-backup"], "(restore-backup)", id="restore-backup"),
    pytest.param(["compute", "instances", "stop"], "(stop)", id="stop"),
    pytest.param(["compute", "instances", "suspend"], "(suspend)", id="suspend"),
    pytest.param(["ai", "endpoints", "undeploy-model"], "(undeploy-model)", id="undeploy"),
    pytest.param(["compute", "instance-groups", "managed", "abandon-instances"], "(abandon-instances)",
                 id="abandon"),
    pytest.param(["privateca", "certificates", "revoke"], "(revoke)", id="revoke"),
    pytest.param(["run", "services", "add-iam-policy-binding"], "reaches iam", id="add-iam-policy-binding"),
    pytest.param(["run", "services", "set-iam-policy"], "reaches iam", id="set-iam-policy"),
    pytest.param(["projects", "add-iam-policy-binding"], "reaches projects", id="project-iam"),
    pytest.param(["organizations", "add-iam-policy-binding"], "reaches organizations", id="organization-iam"),
    pytest.param(["iam", "service-accounts", "create"], "reaches iam", id="service-accounts"),
    pytest.param(["compute", "instances", "set-service-account"], "reaches service-account",
                 id="set-service-account"),
    pytest.param(["iam", "roles", "create"], "reaches iam", id="roles"),
    pytest.param(["services", "api-keys", "create"], "reaches keys", id="api-keys"),
    pytest.param(["secrets", "create"], "reaches secrets", id="secrets"),
    pytest.param(["kms", "keys", "create"], "reaches kms", id="kms"),
    pytest.param(["billing", "budgets", "create"], "reaches billing", id="billing"),
    pytest.param(["folders", "create"], "reaches folders", id="folders"),
    pytest.param(["resource-manager", "tags", "create"], "reaches resource-manager", id="resource-manager"),
    pytest.param(["projects", "create"], "reaches projects", id="projects"),
    pytest.param(["compute", "ssh"], "reaches ssh", id="ssh"),
    pytest.param(["compute", "scp"], "reaches scp", id="scp"),
    pytest.param(["compute", "start-iap-tunnel"], "reaches iap", id="iap-tunnel"),
    pytest.param(["workstations", "start-tcp-tunnel"], "reaches tunnel", id="tunnel"),
    pytest.param(["run", "services", "proxy"], "reaches proxy", id="proxy"),
    pytest.param(["iap", "settings", "set"], "reaches iap", id="iap"),
    pytest.param(["workstations", "port-forward"], "reaches port-forward", id="port-forward"),
    pytest.param(["sql", "connect"], "reaches connect", id="connect"),
    pytest.param(["access-approval", "settings", "update"], "reaches access-approval", id="access-approval"),
    pytest.param(["org-policies", "set-policy"], "reaches org-policies", id="org-policies"),
    pytest.param(["identity", "groups", "create"], "reaches identity", id="identity"),
    pytest.param(["pam", "entitlements", "create"], "reaches pam", id="pam"),
    pytest.param(["access-context-manager", "policies", "create"], "reaches access-context-manager",
                 id="access-context-manager"),
    pytest.param(["compute", "firewall-rules", "create"], "reaches firewall-rules", id="firewall-rules"),
    pytest.param(["compute", "instances", "add-access-config"], "reaches config", id="access-config"),   # `config` holds it first
    pytest.param(["compute", "instances", "add-metadata"], "reaches metadata", id="metadata"),
    pytest.param(["sql", "users", "set-password"], "reaches password", id="password"),
    pytest.param(["scc", "notifications", "create"], "reaches scc", id="scc"),
    pytest.param(["storage", "cp"], "reaches storage", id="storage"),
    pytest.param(["container", "clusters", "get-credentials"], "credential", id="sensitive-word"),
]


@pytest.mark.parametrize("path, why", NEVER_PATHS)
def test_a_path_that_is_never_covered_is_refused_at_create_naming_it(path, why):
    with pytest.raises(mandate.MandateError, match=re.escape(f"gcloud {' '.join(path)}") + ".*always asks on a card"):
        mandate.terms(**{**GOOD, "commands": [path]})
    assert why in mandate.never(judge(path))


def test_the_never_covered_words_cover_what_the_decision_names():
    assert {"delete", "remove", "destroy", "purge", "reset", "cancel", "disable", "undelete", "rm", "restore",
            "stop", "suspend", "undeploy", "abandon", "revoke", "replace"} <= set(mandate.NEVER_ENDINGS)
    assert {"project", "projects", "namespace", "password"} <= set(mandate.NEVER_FLAG_WORDS)
    assert "builds" in mandate.NEVER_WORDS
    assert {"service-accounts", "service-account", "keys", "secrets", "kms", "billing", "organizations",
            "folders", "projects", "resource-manager", "auth", "config", "ssh", "scp", "port-forward", "connect",
            "access-approval", "org-policies", "iap", "iam", "tunnel", "proxy", "identity", "pam",
            "access-context-manager", "firewall-rules", "access-config", "metadata", "password", "scc",
            "storage"} <= set(mandate.NEVER_WORDS)
    assert mandate._holds("start-iap-tunnel", "iap") and mandate._holds("get-iam-policy", "iam")
    assert not mandate._holds("connectors", "connect") and not mandate._holds("monkeys", "keys")


# The families of flags no mandate lists (the review's findings, whole), and the flags named there.
NEVER_FLAGS = [
    "--ingress", "--ingress-settings", "--egress-settings", "--direct-vpc-egress", "--service-account",
    "--run-service-account", "--build-service-account", "--trigger-service-account", "--impersonate-service-account",
    "--security-level", "--no-iap", "--iap", "--breakglass", "--clear-network", "--network", "--network-tags",
    "--vpc-connector", "--clear-vpc-connector", "--subnet", "--subnetwork", "--key", "--clear-key", "--keys",
    "--kms-key", "--clear-kms-key", "--predefined-acl", "--acl", "--pap", "--public-access-prevention",
    "--scopes", "--metadata", "--metadata-from-file", "--assign-ip", "--no-assign-ip", "--no-require-ssl",
    "--require-ssl", "--ssl-mode", "--address", "--source-ranges", "--authorized-networks", "--add-custom-audiences",
    "--set-custom-audiences", "--audiences", "--add-cloudsql-instances", "--set-cloudsql-instances",
    "--workload-pool", "--legacy-authorization", "--identity", "--organization", "--folder", "--billing-project",
    "--account", "--configuration", "--delete-labels", "--delete-protection", "--no-delete-protection",
    "--member", "--role", "--roles", "--add-iam-policy-binding", "--no-invoker-iam-check", "--invoker-iam-check",
    "--allow-unauthenticated", "--no-allow-unauthenticated", "--set-secrets", "--update-secrets",
    "--remove-secrets", "--clear-secrets", "--binary-authorization", "--clear-binary-authorization",
    "--source", "--env-vars-file", "--build-env-vars-file", "--ignore-file", "--flags-file", "--output-file",
    "--rbac-output-file", "--ssh-key-file", "--output-dir", "--cache-dir", "--config-directory", "--config-path",
    "--file", "--add-volume", "--add-volume-mount", "--stage-bucket", "--public", "--no-public",
    "--default-service-account", "--image-project", "--source-project", "--target-project",
    "--destination-project", "--host-project", "--namespace", "--password", "--root-password", "--projects",
    "--password-policy-min-length", "--node-project",
]


@pytest.mark.parametrize("flag", NEVER_FLAGS)
def test_a_flag_of_a_never_covered_family_can_never_be_listed(flag):
    assert mandate.never_flag(flag), flag


def test_ordinary_flags_are_in_no_family():
    for flag in ("--image", "--region", "--memory", "--cpu", "--tag", "--set-env-vars", "--update-labels",
                 "--remove-labels", "--max-instances", "--min-instances", "--timeout", "--concurrency",
                 "--no-traffic", "--cpu-throttling", "--no-cpu-throttling", "--format", "--async", "--port",
                 "--args", "--revision-suffix", "--runtime", "--entry-point", "--trigger-http"):
        assert mandate.never_flag(flag) is None, flag


@pytest.mark.parametrize("flag", NEVER_FLAGS)
def test_a_never_covered_flag_is_refused_at_create_whether_or_not_the_tree_declares_it(flag):
    with pytest.raises(mandate.MandateError, match="always asks on a card"):
        mandate.terms(**{**GOOD, "flags": [flag]})


@pytest.mark.parametrize("flag", sorted(access.GCLOUD_WRITE_FLAGS))
def test_a_flag_that_writes_a_local_file_is_refused_at_create(flag):
    with pytest.raises(mandate.MandateError, match="always asks on a card"):
        mandate.terms(**{**GOOD, "flags": [flag]})


@pytest.mark.parametrize("flag", ["--project", "--impersonate-service-account", "--flags-file", "--log-http"])
def test_a_flag_the_tool_forbids_is_refused_at_create(flag):
    with pytest.raises((mandate.MandateError, access.AccessError)):
        mandate.terms(**{**GOOD, "flags": [flag]})


def test_the_store_holds_every_mandate_to_seven_days_in_a_scope_no_profile_receives():
    assert mandate.STORE.max_days == 7 and mandate.STORE.mac_kind == "gcloud-mandate"
    assert mandate.STORE.key_prefix == "GCLOUD_MANDATE_KEY_" and mandate.STORE.scope == "google-access"
    assert mandate.STORE.state == access.STATE_DIR and mandate.LEDGER_KIND == "gcloud-use"


def test_the_card_shows_every_bound(monkeypatch):
    t = mandate.terms(**{**GOOD, "per_hour": 7, "days": 1})
    monkeypatch.setattr(mandate.cards, "budget", lambda where=None: mandate.cards.ROOMY["telegram"])
    card = mandate.card(t)
    bounds = card.rsplit("\nNever covered", 1)[0]
    monkeypatch.setattr(mandate.cards, "budget", lambda where=None: mandate.cards.units(bounds))
    assert mandate.card(t) == bounds   # the shared rule gives way first on a short card
    assert card.startswith("gcloud · Project mandate\n🚨 These commands skip the card in this project\n")
    assert f"Project: {PROJECT}\nCommand: gcloud run deploy\nCommand: gcloud run services update\n" in card
    assert "\nFlags: --image, --region\nUp to: 7 commands an hour" in card and "(1 day)" in card
    assert "Purpose: Ship the staging service" in card
    assert "Never covered: deletes and stops, IAM and service accounts, secrets and keys, billing, projects and " in card
    assert "\nFlags: none\n" in mandate.card(mandate.terms(**{**GOOD, "flags": []}))


def test_a_card_that_cannot_show_every_bound_is_refused(monkeypatch):
    monkeypatch.setattr(mandate.cards, "budget", lambda where=None: 100)
    with pytest.raises(mandate.MandateError, match="cannot show all its bounds"):
        mandate.card(mandate.terms(**GOOD))


# --- making, listing and ending one ---------------------------------------------------------------

def test_a_mandate_is_made_on_its_own_card_listed_and_revoked(rig):
    directive, result = rig.call("gcloud_mandate", create())
    assert directive["action"] == "approve" and directive["message"].startswith("gcloud · Project mandate\n🚨 ")
    assert directive["rule_key"].startswith("google-access:mandate:")
    made = result["mandate"]
    assert result["ok"] is True and made["project"] == PROJECT and made["per_hour"] == 5
    assert made["commands"] == ["run deploy", "run services update"]
    assert rig.listed() == [made]
    assert re.fullmatch(r"[0-9a-f]{64}", rig.keyfile.read_text().strip())   # the first mandate made the key
    assert (rig.home / "google-access" / "uses.jsonl").is_file()
    _, ended = rig.call("gcloud_mandate", {"action": "revoke", "mandate": made["id"]})
    assert ended == {"ok": True, "revoked": made["id"]} and rig.listed() == []


def test_a_bad_mandate_id_is_not_revoked(rig):
    _, result = rig.call("gcloud_mandate", {"action": "revoke", "mandate": "nope"})
    assert result["ok"] is False and "mandate is an id like" in result["error"]


def test_every_mandate_asks_with_a_fresh_key_even_beside_one_in_force(rig):
    rig.make()
    keys = {rig.call("gcloud_mandate", create(), approve=False)[0]["rule_key"] for _ in range(3)}
    assert len(keys) == 3


def test_a_mandate_is_made_only_after_its_card(rig):
    result = json.loads(rig.handlers["gcloud_mandate"](create()))
    assert result["ok"] is False and "only on its own card" in result["error"] and rig.listed() == []
    rig.gate(tool_name="gcloud_mandate", args=create(days=2), tool_call_id="x")
    other = json.loads(rig.handlers["gcloud_mandate"](create()))   # a card for different terms is no card
    assert other["ok"] is False and rig.listed() == []


def test_a_denied_card_makes_nothing(rig):
    directive, result = rig.call("gcloud_mandate", create(), approve=False)
    assert directive["action"] == "approve" and result is None and rig.listed() == []


def test_nobody_to_answer_no_mandate(rig):
    rig.nobody = "this is a cron job"
    directive, _ = rig.call("gcloud_mandate", create())
    assert directive["action"] == "block" and "this is a cron job" in directive["message"]
    rig.nobody = None
    rig.gate(tool_name="gcloud_mandate", args=create(), tool_call_id="call-9")
    rig.nobody = "yolo mode is on"
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "call-9")
    result = json.loads(rig.handlers["gcloud_mandate"](create()))
    assert result["ok"] is False and "yolo mode is on" in result["error"] and rig.listed() == []
    assert not (rig.home / "google-access" / "head.json").exists()


def test_a_mandate_never_makes_a_mandate(rig):
    rig.make()
    rig.nobody = "this is a cron job"
    assert rig.call("gcloud_mandate", create())[0]["action"] == "block"   # held for its own card, always


def test_inbound_a2a_makes_lists_revokes_and_runs_nothing(rig):
    made = rig.make()
    rig.monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for args in (create(), {"action": "list"}, {"action": "revoke", "mandate": made["id"]}):
        directive = rig.gate(tool_name="gcloud_mandate", args=args, tool_call_id="a")
        assert directive["action"] == "block" and "A2A" in directive["message"]
        assert "A2A" in json.loads(rig.handlers["gcloud_mandate"](args))["error"]
    assert rig.gate(tool_name="gcloud", args=deploy(), tool_call_id="a")["action"] == "block"
    rig.monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    assert [m["id"] for m in rig.listed()] == [made["id"]]


def test_a_path_that_changed_between_the_card_and_the_handler_makes_nothing(rig):
    rig.gate(tool_name="gcloud_mandate", args=create(), tool_call_id="call-1")
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "call-1")
    rig.monkeypatch.setattr(access, "_command_tree", lambda: tree({"run": {"deploy": None}}))
    result = json.loads(rig.handlers["gcloud_mandate"](create()))
    assert result["ok"] is False and rig.listed() == []


@pytest.mark.parametrize("over, message", [
    ({"commands": [["run", "services", "delete"]]}, "always asks on a card"),
    ({"commands": [["run", "services", "list"]]}, "is a read"),
    ({"commands": [["run", "deploy"]] * 2}, "named twice"),
    ({"commands": [["run", "nowhere"]]}, "not a gcloud command path"),
    ({"commands": [["storage", "rm"]]}, "always asks on a card"),
    ({"flags": ["--service-account"]}, "always asks on a card"),
    ({"flags": ["--nope"]}, "not a flag of any"),
    ({"project": "a-proj b-proj"}, "not a project id"),
    ({"per_hour": 11}, "per_hour"),
    ({"days": 8}, "days"),
    ({"mandate": "m00000000"}, "does not take mandate"),
    ({"service_account": "x"}, "does not take service_account"),
])
def test_terms_that_are_refused_never_reach_a_card(rig, over, message):
    directive = rig.gate(tool_name="gcloud_mandate", args=create(**over), tool_call_id="x")
    assert directive["action"] == "block" and message in directive["message"]
    assert rig.listed() == []


def test_the_mandate_tool_is_the_assistants_only():
    ctx = Ctx("creator")
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == []
    ctx = Ctx("assistant")
    plugin.register(ctx)
    tool = ctx.tools["gcloud_mandate"]
    schema = tool["schema"]["parameters"]
    assert schema["additionalProperties"] is False and schema["required"] == ["action"]
    assert schema["properties"]["action"]["enum"] == ["create", "list", "revoke"]
    assert schema["properties"]["commands"]["maxItems"] == 5 and schema["properties"]["flags"]["maxItems"] == 20
    assert set(schema["properties"]) == {"action", "project", "commands", "flags", "per_hour", "days", "purpose",
                                         "mandate"}
    assert tool["emoji"] and tool["toolset"] == "google_access"


def test_the_progress_line_of_the_mandate_tool_shows_the_action_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx("assistant"))
    line = lambda **args: display.build_tool_preview("gcloud_mandate", args, max_len=0)
    assert line(action="create", project="secret-project", purpose="the merger") == "create"
    assert line(action="revoke", mandate="m1a2b3c4d") == "revoke"
    assert line(action="anything") is None


# --- commands that fit a mandate ------------------------------------------------------------------

@pytest.mark.parametrize("nobody", [None, "this is a cron job"], ids=["attended", "unattended"])
def test_a_covered_command_runs_with_no_card_once_and_is_counted(rig, nobody):
    made = rig.make()
    rig.nobody = nobody
    directive, result = rig.gcloud(deploy())
    assert directive is None and result["ok"] is True, result
    assert rig.ran == [["/bin/gcloud", "run", "deploy", "--quiet", f"--project={PROJECT}", "svc",
                        "--image=gcr.io/my-proj/app", "--region=asia-northeast1"]]
    assert rig.used(made["id"]) == 1
    assert access._GCLOUD_APPROVED == {}   # the record is spent
    again = json.loads(rig.handlers["gcloud"](deploy()))   # the same call again, with no hook: not recorded
    assert again["ok"] is False and len(rig.ran) == 1 and rig.used(made["id"]) == 1


def test_the_second_command_of_a_mandate_is_covered_too(rig):
    made = rig.make()
    rig.nobody = "this is a cron job"
    directive, result = rig.gcloud(deploy(command=("run", "services", "update")))
    assert directive is None and result["ok"] is True and rig.used(made["id"]) == 1


def test_the_gate_records_the_mandate_and_the_handler_peeks_without_spending_it(rig):
    made = rig.make()
    rig.nobody = "this is a cron job"
    assert rig.gate(tool_name="gcloud", args=deploy(), tool_call_id="c1") is None
    assert access.covered_by_mandate(deploy(), "c1") and access.covered_by_mandate(deploy(), "c1")
    assert not access.covered_by_mandate(deploy(), "c2") and not access.covered_by_mandate(deploy("--x"), "")
    [(_, _, recorded)] = access._GCLOUD_APPROVED.values()
    assert recorded == made["id"]


def test_a_command_without_a_call_id_is_recorded_by_its_arguments(rig):
    made = rig.make()
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "")
    assert rig.gate(tool_name="gcloud", args=deploy()) is None
    assert json.loads(rig.handlers["gcloud"](deploy()))["ok"] is True and rig.used(made["id"]) == 1


def test_the_hours_last_slot_goes_to_one_and_the_next_asks(rig):
    made = rig.make(per_hour=2)
    for n in range(2):
        rig.nobody = "this is a cron job" if n else None
        directive, result = rig.gcloud(deploy())
        assert directive is None and result["ok"] is True
    assert rig.used(made["id"]) == 2
    rig.nobody = None
    directive, _ = rig.gcloud(deploy())
    assert directive["action"] == "approve"   # a card, as before
    rig.nobody = "this is a cron job"
    directive, result = rig.gcloud(deploy())
    assert directive["action"] == "block" and "cron job" in directive["message"] and result is None
    assert len(rig.ran) == 3 and rig.used(made["id"]) == 2   # two on the mandate, one on its card
    call = access.gcloud_call(deploy())
    assert mandate.covering(rig.home, call)[0] is None
    assert mandate.covering(rig.home, call, now=time.time() + HOUR + 60)[0] == made["id"]


def test_ten_an_hour_is_the_ceiling_and_the_eleventh_asks(rig):
    made = rig.make(per_hour=10)
    for n in range(10):
        rig.nobody = "this is a cron job" if n % 2 else None
        assert rig.gcloud(deploy())[1]["ok"] is True
    assert rig.used(made["id"]) == 10
    rig.nobody = None
    assert rig.gcloud(deploy())[0]["action"] == "approve"   # the eleventh asks; here the card is answered
    rig.nobody = "this is a cron job"
    assert rig.gcloud(deploy())[0]["action"] == "block"
    assert len(rig.ran) == 11 and rig.used(made["id"]) == 10


def test_two_mandates_the_second_takes_what_the_first_cannot(rig):
    first, second = rig.make(per_hour=1), rig.make(per_hour=1)
    rig.gcloud(deploy())
    rig.gcloud(deploy())
    assert {rig.used(first["id"]), rig.used(second["id"])} == {1}
    rig.nobody = "this is a cron job"
    assert rig.gcloud(deploy())[0]["action"] == "block"


def test_a_failed_command_still_counts(rig):
    made = rig.make()
    rig.exit_code = 1
    _, result = rig.gcloud(deploy())
    assert result["ok"] is False and result["exit_code"] == 1 and rig.used(made["id"]) == 1


def test_a_covered_command_runs_in_an_empty_private_directory_that_is_gone_afterwards(rig):
    rig.make()
    assert rig.gcloud(deploy())[1]["ok"] is True
    [seen] = rig.cwds
    cwd, held, mode = seen
    assert held == [] and mode == 0o700 and Path(cwd).is_absolute()
    assert Path(cwd).resolve() != Path.cwd().resolve() and not Path(cwd).exists()
    assert rig.gcloud(deploy())[1]["ok"] is True
    assert rig.cwds[1][0] != cwd   # a fresh one each time


@pytest.mark.parametrize("how", [1, "timeout"], ids=["fails", "times out"])
def test_the_directory_of_a_covered_command_is_removed_however_it_ends(rig, how):
    rig.make()
    rig.exit_code = how
    rig.gcloud(deploy())
    [(cwd, _, _)] = rig.cwds
    assert not Path(cwd).exists()


def test_a_command_that_asked_on_its_card_keeps_the_working_directory(rig):
    directive, result = rig.gcloud(deploy())   # no mandate: a card, answered
    assert directive["action"] == "approve" and result["ok"] is True
    assert rig.cwds == [None]
    rig.make()
    assert rig.gcloud(deploy("--cpu=2"))[0]["action"] == "approve"   # not covered: a card again
    assert rig.cwds == [None, None]


def test_a_read_keeps_the_working_directory(rig):
    rig.make()
    rig.gcloud({"command": ["run", "services", "list"], "project": PROJECT})
    assert rig.cwds == [None]


def test_a_mandate_covers_only_its_commands(rig):
    rig.make(commands=[["run", "deploy"]])
    rig.nobody = "this is a cron job"
    assert rig.gcloud(deploy(command=("run", "services", "update")))[0]["action"] == "block"
    assert rig.gcloud(deploy(command=("functions", "deploy")))[0]["action"] == "block"
    assert rig.gcloud(deploy())[0] is None


def test_a_release_track_is_a_path_of_its_own(rig):
    rig.make(commands=[["run", "deploy"]])
    rig.nobody = "this is a cron job"
    assert rig.gcloud(deploy(command=("beta", "run", "deploy")))[0]["action"] == "block"
    rig.nobody = None
    rig.make(commands=[["beta", "run", "deploy"]])
    rig.nobody = "this is a cron job"
    assert rig.gcloud(deploy(command=("beta", "run", "deploy")))[0] is None
    assert rig.gcloud(deploy(command=("alpha", "run", "deploy")))[0]["action"] == "block"


def test_another_project_and_no_project_ask(rig):
    made = rig.make()
    rig.nobody = "this is a cron job"
    assert rig.gcloud(deploy(project="other-proj"))[0]["action"] == "block"
    assert rig.gcloud(deploy(project=None))[0]["action"] == "block"
    call = access.gcloud_call(deploy(project=None))
    assert "without a project is never covered" in mandate.covering(rig.home, call)[1][0]
    assert rig.ran == [] and rig.used(made["id"]) == 0


NEVER_ARGS = [
    ["--allow-unauthenticated"], ["--allow-unauthenticated=true"], ["--ingress=all"], ["--ingress", "all"],
    ["--no-invoker-iam-check"], ["--member=user:x@example.com"], ["--role=roles/owner"],
    ["--service-account=runner@my-proj.iam.gserviceaccount.com"], ["--set-secrets=K=s:latest"],
    ["--update-secrets=K=s:1"], ["--remove-secrets=K"], ["--clear-secrets"], ["--binary-authorization=default"],
    ["--clear-binary-authorization"], ["--vpc-connector=c"], ["--network=default"], ["--subnet=s"],
    ["--vpc-egress=all-traffic"], ["--public"], ["--authorized-networks=1.2.3.4/32"],
    ["--allow-unauthenticated-invocations"], ["--add-iam-policy-binding=x"], ["--output-file=out.json"],
    ["--destination", "out"],
]


@pytest.mark.parametrize("extra", NEVER_ARGS, ids=lambda extra: " ".join(extra))
def test_a_flag_the_mandate_does_not_list_makes_the_same_path_ask(rig, extra):
    made = rig.make()
    args = deploy(*extra)
    directive = rig.gate(tool_name="gcloud", args=args, tool_call_id="c1")
    assert directive["action"] == "approve" and directive["message"].startswith("gcloud · Run a command")
    assert [recorded for _, _, recorded in access._GCLOUD_APPROVED.values()] == [None]
    rig.nobody = "this is a cron job"
    blocked = rig.gate(tool_name="gcloud", args=args, tool_call_id="c2")
    assert blocked["action"] == "block" and "cron job" in blocked["message"]
    assert not access.covered_by_mandate(args, "c2")
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "c2")
    assert json.loads(rig.handlers["gcloud"](args))["ok"] is False
    assert rig.ran == [] and rig.used(made["id"]) == 0


@pytest.mark.parametrize("flag", [f for f in NEVER_FLAGS if f not in access.GCLOUD_FORBIDDEN_FLAGS])
def test_a_stored_mandate_that_lists_a_never_covered_flag_still_does_not_cover_it(flag, monkeypatch):
    """Even a list written by a version without the rule (the store is trusted, the rule is checked again):
    the tree declares the flag, so the call reads, and it is the family check at the fit that refuses it."""
    leaf = {"commands": {}, "flags": {flag: "value"}}
    monkeypatch.setattr(access, "_command_tree", lambda: {"flags": ROOT_FLAGS, "commands": {
        "run": {"commands": {"deploy": leaf}, "flags": {}}}})
    m = {"project": PROJECT, "commands": [["run", "deploy"]], "flags": [flag]}
    call = access.gcloud_call(with_args("svc", f"{flag}=x"))
    assert call.unparsed is None and call.flags == ((flag, "x"),)
    why = mandate.fits(m, call)
    assert why and why == (mandate.never(call) or mandate.never_flag(flag)), (flag, why)


@pytest.mark.parametrize("flag", sorted(access.GCLOUD_WRITE_FLAGS))
def test_a_stored_mandate_that_lists_a_file_writing_flag_is_refused_by_the_write_flag_rule(flag, monkeypatch):
    leaf = {"commands": {}, "flags": {flag: "value"}}
    monkeypatch.setattr(access, "_command_tree", lambda: {"flags": ROOT_FLAGS, "commands": {
        "run": {"commands": {"deploy": leaf}, "flags": {}}}})
    m = {"project": PROJECT, "commands": [["run", "deploy"]], "flags": [flag]}
    call = access.gcloud_call(with_args("svc", f"{flag}=out"))
    assert call.writes_file and call.unparsed is None
    assert mandate.fits(m, call) == "a flag that writes a local file always asks on a card"


def test_a_stored_mandate_that_lists_destination_is_refused_for_the_write_flag_branch_not_the_family(rig):
    """`--destination` is in no word family: only the write-flag branch (never(call)) refuses it."""
    assert mandate.never_flag("--destination") is None
    made = mandate.mandate_store.create(mandate.STORE, rig.home, {
        "project": PROJECT, "commands": [["run", "deploy"]], "flags": ["--destination", "--image"],
        "per_hour": 5, "purpose": "x"}, int(time.time()) + HOUR)
    mandate.mandate_ledger.anchor(mandate.STORE, rig.home, mandate.mandate_store.key(mandate.STORE, rig.home),
                                  mandate.LEDGER_KIND, made["id"], made["created"])
    rig.nobody = "this is a cron job"
    call = access.gcloud_call(with_args("svc", "--destination=out"))
    assert mandate.fits(made, call) == "a flag that writes a local file always asks on a card"
    assert rig.gcloud(with_args("svc", "--destination=out"))[0]["action"] == "block"
    assert rig.gcloud(with_args("svc", "--destination", "out"))[0]["action"] == "block"
    assert rig.ran == []


@pytest.mark.parametrize("extra", [["--memory=512Mi"], ["--memory", "512Mi"], ["--set-env-vars=A=B,C=D"],
                                   ["--format=json"], ["--no-cpu-throttling"], ["--tag=blue", ],
                                   ["--tag=gcr.io/my-proj/app"],
                                   ["--image=asia-docker.pkg.dev/my-proj/repo/img:tag"],
                                   ["--image=gcr.io/my-proj/app"], ["--image=us.gcr.io/my-proj/app:1.2"],
                                   ["--image=GCR.IO/my-proj/app"], ["--image", "eu.gcr.io/MY-PROJ/a/b"],
                                   ["--base-image=gcr.io/my-proj/base"], ["--image-url=gcr.io/my-proj/x"],
                                   ["--pack=image=gcr.io/my-proj/app"],
                                   ["--pack=image=gcr.io/my-proj/app,builder=us-docker.pkg.dev/my-proj/b/c,env=A=B"]],
                         ids=lambda extra: " ".join(extra))
def test_a_listed_flag_with_a_plain_value_stays_covered(rig, extra):
    made = rig.make(flags=[*LISTED, "--tag", "--base-image", "--image-url", "--pack"])
    rig.nobody = "this is a cron job"
    args = {"command": ["run", "deploy"], "project": PROJECT, "args": ["svc", *extra]}
    directive, result = rig.gcloud(args)
    assert directive is None and result["ok"] is True and rig.used(made["id"]) == 1


def asks(rig, args):
    """The call is not covered: the hook refuses it where nobody can answer a card, and nothing runs."""
    rig.nobody = "this is a cron job"
    before = len(rig.ran)
    directive, result = rig.gcloud(args)
    assert directive["action"] == "block" and "cron job" in directive["message"] and result is None, args
    assert len(rig.ran) == before


def with_args(*extra, command=("run", "deploy")):
    return {"command": list(command), "project": PROJECT, "args": list(extra)}


@pytest.mark.parametrize("extra", [["svc", "--cpu=2"], ["svc", "--tag=blue"], ["svc", "--no-traffic"],
                                   ["svc", "--async"], ["svc", "--nope=1"], ["svc", "--no-memory"],
                                   ["svc", "--verbosity=debug"], ["svc", "--quiet"]],
                         ids=lambda extra: " ".join(extra))
def test_a_flag_the_mandate_does_not_list_or_the_tree_does_not_know_asks(rig, extra):
    rig.make()
    asks(rig, with_args(*extra))


@pytest.mark.parametrize("value", ["/etc/passwd", "~/x", "./x", "../x", "gs://bucket/x", "projects/OTHER/x",
                                   "https://example.com/projects/OTHER/x", "a/../b", "organizations/1",
                                   "folders/2", "a b", "", "-x", "x;rm", "$(id)", "a" * 301, "x/projects/y"])
def test_a_listed_flag_with_a_path_url_or_other_resource_as_value_asks(rig, value):
    rig.make()
    asks(rig, with_args("svc", f"--image={value}"))
    if value and not value.startswith("-"):
        asks(rig, with_args("svc", "--memory", value))


NOT_THE_PROJECTS_IMAGE = [
    "gcr.io/other/app", "us.gcr.io/other/app:1", "eu.gcr.io/other/a/b", "asia-docker.pkg.dev/other/repo/img:tag",
    "mirror.gcr.io/library/x", "mirror.gcr.io/my-proj/x", "evil.gcr.io/my-proj/x", "GCR.IO/other/app",
    "Asia-Docker.Pkg.Dev/OTHER/r/i",
    "docker.io/library/nginx:1.27", "ghcr.io/owner/app", "quay.io/my-proj/app", "nginx", "nginx:1.27", "library/nginx",
    "my-proj/app", "gcr.io:443/my-proj/app", "gcr.io./my-proj/app", "gcr.io/my-proj", "gcr.io//app",
    "gcr.io/my-proj.evil/app", "docker.pkg.dev/my-proj/r/i", "us-docker.pkg.dev:443/my-proj/r/i",
    "us-docker.pkg.dev./my-proj/r/i", "http:/gcr.io/my-proj/x",
]


@pytest.mark.parametrize("image", NOT_THE_PROJECTS_IMAGE)
@pytest.mark.parametrize("flag", ["--image", "--base-image", "--image-url"])
def test_an_image_flag_value_that_is_not_in_the_projects_registry_asks(rig, flag, image):
    rig.make(flags=[*LISTED, "--base-image", "--image-url"])
    asks(rig, with_args("svc", f"{flag}={image}"))
    asks(rig, with_args("svc", flag, image))


@pytest.mark.parametrize("value", ["gcr.io/other/app", "GCR.IO/other/app", "us-docker.pkg.dev/other/r/i",
                                   "gcr.io:443/my-proj/app", "gcr.io./my-proj/app", "mirror.gcr.io/library/x"])
def test_any_other_value_that_starts_like_a_google_registry_must_be_in_the_project_too(rig, value):
    rig.make(flags=[*LISTED, "--tag"])
    asks(rig, with_args("svc", f"--tag={value}"))


@pytest.mark.parametrize("value", ["image=docker.io/library/nginx", "image=gcr.io/other/app", "image=nginx",
                                   "image=gcr.io/my-proj/app,builder=gcr.io/buildpacks/builder:v1",
                                   "image=gcr.io/my-proj/app,builder=nginx", "builder=gcr.io/my-proj/b",
                                   "env=A=B", "image=gcr.io/my-proj/app,IMAGE=docker.io/x",
                                   "image=docker.io/x,image=gcr.io/my-proj/app", "IMAGE=GCR.IO/other/x"])
def test_a_pack_value_must_name_its_image_and_builder_in_the_projects_registry(rig, value):
    rig.make(flags=[*LISTED, "--pack"])
    asks(rig, with_args("svc", f"--pack={value}"))


@pytest.mark.parametrize("positional", ["svc/x", "Svc", ".", "..", "../x", "/etc", "~", "-", "a b", "x" * 64,
                                        "gs://b", "projects/OTHER/services/svc", "svc\\x"])
def test_a_positional_that_is_not_a_plain_resource_id_asks(rig, positional):
    rig.make()
    asks(rig, with_args(positional, "--region=asia-northeast1"))


@pytest.mark.parametrize("extra", [["svc", "--"], ["svc", "--", "--image=x"], ["svc", "-q"], ["svc", "-x", "y"],
                                   ["-", "svc"], ["svc", "--image"], ["svc", "--image", "--region=x"],
                                   ["svc", "--image="]])
def test_the_end_of_flags_a_short_flag_and_a_flag_without_its_value_ask(rig, extra):
    rig.make()
    asks(rig, with_args(*extra))


def test_both_forms_of_a_listed_flag_are_covered_and_a_negation_only_when_listed(rig):
    made = rig.make()
    rig.nobody = "this is a cron job"
    assert rig.gcloud(with_args("svc", "--memory", "1Gi", "--region=asia-northeast1"))[1]["ok"] is True
    assert rig.used(made["id"]) == 1
    asks(rig, with_args("svc", "--no-traffic"))   # the tree lists it, the mandate does not
    rig.nobody = None
    rig.make(flags=[*LISTED, "--no-traffic"])
    rig.nobody = "this is a cron job"
    assert rig.gcloud(with_args("svc", "--no-traffic"))[1]["ok"] is True


def test_the_arguments_are_read_as_the_tree_lists_them():
    call = access.gcloud_call(with_args("svc", "--memory", "1Gi", "--no-cpu-throttling", "--async",
                                        "--region=asia-northeast1"))
    assert call.flags == (("--memory", "1Gi"), ("--no-cpu-throttling", None), ("--async", None),
                          ("--region", "asia-northeast1"))
    assert call.positionals == ("svc",) and call.unparsed is None
    assert call.kind("--no-cpu-throttling") == "bool" and call.kind("--memory") == "value"
    assert call.kind("--no-memory") is None and call.kind("--nope") is None
    assert "--nope" in access.gcloud_call(with_args("--nope")).unparsed
    assert "end of flags" in access.gcloud_call(with_args("--", "x")).unparsed
    assert "short flag" in access.gcloud_call(with_args("-q")).unparsed
    assert "no value" in access.gcloud_call(with_args("--memory")).unparsed
    assert "no value" in access.gcloud_call(with_args("--memory", "--region=x")).unparsed


@pytest.mark.parametrize("switch", ["--async=true", "--async=false", "--async=", "--no-cpu-throttling=true",
                                    "--cpu-throttling=1", "--no-traffic=x"])
def test_a_switch_written_with_a_value_is_not_read_and_asks(rig, switch):
    call = access.gcloud_call(with_args("svc", switch))
    assert "takes no =value" in call.unparsed
    rig.make(flags=[*LISTED, "--async", "--cpu-throttling", "--no-traffic"])
    asks(rig, with_args("svc", switch))
    rig.nobody = "this is a cron job"
    assert rig.gcloud(with_args("svc", "--async"))[1]["ok"] is True   # the bare switch is covered


def test_listing_a_negation_does_not_cover_the_switch_nor_the_other_way_round(rig):
    first = rig.make(flags=["--image", "--no-cpu-throttling"])
    asks(rig, with_args("svc", "--cpu-throttling"))
    rig.nobody = None
    rig.call("gcloud_mandate", {"action": "revoke", "mandate": first["id"]})
    rig.make(flags=["--image", "--cpu-throttling"])
    asks(rig, with_args("svc", "--no-cpu-throttling"))
    rig.nobody = "this is a cron job"
    assert rig.gcloud(with_args("svc", "--cpu-throttling"))[1]["ok"] is True


def test_a_flag_declared_on_only_one_of_two_mandated_paths_is_covered_on_that_path_only(rig, monkeypatch):
    def leaf(*flags):
        return {"commands": {}, "flags": {flag: "value" for flag in flags}}
    monkeypatch.setattr(access, "_command_tree", lambda: {"flags": ROOT_FLAGS, "commands": {"run": {
        "commands": {"deploy": leaf("--image", "--region", "--memory"),
                     "services": {"commands": {"update": leaf("--image", "--region", "--tag")}, "flags": {}}},
        "flags": {}}}})
    terms = mandate.terms(**{**GOOD, "flags": ["--image", "--memory", "--tag"]})   # each declared by one path
    assert terms["flags"] == ["--image", "--memory", "--tag"]
    rig.make(flags=["--image", "--memory", "--tag"])
    rig.nobody = "this is a cron job"
    update = ("run", "services", "update")
    assert rig.gcloud(with_args("svc", "--memory=1Gi"))[1]["ok"] is True
    assert rig.gcloud(with_args("svc", "--tag=blue", command=update))[1]["ok"] is True
    asks(rig, with_args("svc", "--tag=blue"))                   # run deploy does not declare --tag
    asks(rig, with_args("svc", "--memory=1Gi", command=update))   # run services update does not declare --memory
    assert "not a flag the installed gcloud lists" in mandate.fits(
        mandate.active(rig.home)[0], access.gcloud_call(with_args("svc", "--tag=blue")))


def test_a_mandate_with_no_flags_covers_only_flagless_calls(rig):
    made = rig.make(flags=[])
    rig.nobody = "this is a cron job"
    assert rig.gcloud(with_args("svc"))[1]["ok"] is True and rig.used(made["id"]) == 1
    asks(rig, with_args("svc", "--region=asia-northeast1"))


def test_an_identity_flag_the_tool_forbids_is_blocked_before_a_mandate_is_looked_at(rig):
    rig.make()
    for flag in ("--impersonate-service-account=x@y", "--project=other", "--account=a@b", "--flags-file=f"):
        directive = rig.gate(tool_name="gcloud", args=deploy(flag), tool_call_id="x")
        assert directive["action"] == "block" and "not allowed" in directive["message"]


@pytest.mark.parametrize("path, why", NEVER_PATHS)
def test_a_path_that_is_never_covered_asks_at_the_write_whatever_the_stored_terms(rig, path, why):
    """Even a mandate that somehow names it (stored by a version without the rule) covers nothing."""
    made = mandate.mandate_store.create(mandate.STORE, rig.home, {
        "project": PROJECT, "commands": [path], "flags": [], "per_hour": 5, "purpose": "x"}, int(time.time()) + HOUR)
    mandate.mandate_ledger.anchor(mandate.STORE, rig.home, mandate.mandate_store.key(mandate.STORE, rig.home),
                                  mandate.LEDGER_KIND, made["id"], made["created"])
    rig.nobody = "this is a cron job"
    directive = rig.gate(tool_name="gcloud", args={"command": path, "project": PROJECT}, tool_call_id="c")
    assert directive["action"] == "block" and rig.ran == []
    covering = mandate.covering(rig.home, access.gcloud_call({"command": path, "project": PROJECT}))
    assert covering[0] is None and why in covering[1][0]


def test_reads_run_with_no_card_and_are_not_counted(rig):
    made = rig.make()
    rig.nobody = "this is a cron job"
    directive, result = rig.gcloud({"command": ["run", "services", "list"], "project": PROJECT})
    assert directive is None and result["ok"] is True and len(rig.ran) == 1
    assert rig.used(made["id"]) == 0 and access._GCLOUD_APPROVED == {}


def test_a_mandate_asks_nothing_of_the_keychain_until_one_was_made(rig, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("the Keychain was asked")
    monkeypatch.setattr(mandate.mandate_store, "call_secret", forbidden)
    call = access.gcloud_call(deploy())
    assert mandate.covering(rig.home, call) == (None, []) and mandate.active(rig.home) == []
    directive, _ = rig.gcloud(deploy())
    assert directive["action"] == "approve"


def test_without_a_readable_key_nothing_is_covered(rig):
    rig.make()
    rig.keyfile.unlink()
    assert rig.gcloud(deploy())[0]["action"] == "approve"
    rig.keyfile.write_text("cd" * 32)   # a replaced key puts nothing in force either
    assert rig.gcloud(deploy())[0]["action"] == "approve"


def test_a_ledger_that_is_gone_reads_as_used_up(rig):
    rig.make()
    assert rig.gcloud(deploy())[1]["ok"] is True
    (rig.home / "google-access" / "uses.jsonl").unlink()
    rig.nobody = "this is a cron job"
    assert rig.gcloud(deploy())[0]["action"] == "block"
    assert "cannot be read" in mandate.covering(rig.home, access.gcloud_call(deploy()))[1][0]


def test_a_mandate_that_ended_covers_nothing(rig):
    made = rig.make()
    call = access.gcloud_call(deploy())
    assert mandate.covering(rig.home, call)[0] == made["id"]
    assert mandate.covering(rig.home, call, now=time.time() + 3 * mandate.DAY + 60) == (None, [])


# --- between the hook and the write ---------------------------------------------------------------

def test_a_mandate_revoked_between_the_hook_and_the_write_runs_nothing(rig):
    made = rig.make()
    rig.nobody = "this is a cron job"
    assert rig.gate(tool_name="gcloud", args=deploy(), tool_call_id="call-7") is None
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "call-7")
    mandate.revoke(rig.home, made["id"])
    result = json.loads(rig.handlers["gcloud"](deploy()))
    assert result["ok"] is False and "no longer fits the gcloud mandate" in result["error"]
    assert "no longer in force" in result["error"] and "it will ask on a card" in result["error"]
    assert rig.ran == []


def test_a_command_that_changed_between_the_hook_and_the_write_is_refused_by_its_digest(rig):
    made = rig.make()
    rig.nobody = "this is a cron job"
    assert rig.gate(tool_name="gcloud", args=deploy(), tool_call_id="call-8") is None
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "call-8")
    changed = deploy("--memory=8Gi")
    result = json.loads(rig.handlers["gcloud"](changed))
    assert result["ok"] is False and "changed after its approval card" in result["error"]
    assert rig.ran == [] and rig.used(made["id"]) == 0
    assert json.loads(rig.handlers["gcloud"](deploy()))["ok"] is False   # the record was spent by the attempt


def test_a_path_the_tree_no_longer_confirms_at_the_write_is_refused_by_the_fit(rig):
    made = rig.make()
    rig.nobody = "this is a cron job"
    assert rig.gate(tool_name="gcloud", args=deploy(), tool_call_id="call-5") is None
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "call-5")
    rig.monkeypatch.setattr(access, "_command_tree", lambda: None)
    result = json.loads(rig.handlers["gcloud"](deploy()))
    assert result["ok"] is False and "no longer fits the gcloud mandate" in result["error"]
    assert "could not be checked" in result["error"] and rig.ran == [] and rig.used(made["id"]) == 0


def test_a_command_the_hook_never_saw_is_refused_even_with_a_mandate(rig):
    rig.make()
    rig.nobody = "this is a cron job"
    result = json.loads(rig.handlers["gcloud"](deploy()))
    assert result["ok"] is False and "cron job" in result["error"] and rig.ran == []
    rig.nobody = None
    result = json.loads(rig.handlers["gcloud"](deploy()))
    assert "did not pass its approval card" in result["error"] and rig.ran == []


def test_a_card_record_is_no_mandate_record(rig):
    rig.make(commands=[["functions", "deploy"]])
    rig.gate(tool_name="gcloud", args=deploy(), tool_call_id="call-3")   # no mandate covers it: a card
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "call-3")
    rig.nobody = "this is a cron job"
    result = json.loads(rig.handlers["gcloud"](deploy()))
    assert result["ok"] is False and "cron job" in result["error"] and rig.ran == []


def test_a_probe_records_nothing_and_a_command_with_no_login_keeps_its_record(rig):
    made = rig.make()
    assert access.approval_request("gcloud", deploy(), home=rig.home) == access.Covered(made["id"])
    assert access._GCLOUD_APPROVED == {}
    access.approval_request("gcloud", deploy(), home=rig.home, call_id="k")
    with pytest.raises(access.AccessError, match="gcloud-login"):
        access.gcloud(rig.home.parent / "elsewhere", deploy(), call_id="k")   # refused before the record is used
    assert access.covered_by_mandate(deploy(), "k")


def test_an_unattended_command_with_no_mandate_in_force_reads_nothing(rig, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("the Keychain was asked")
    monkeypatch.setattr(mandate.mandate_store, "call_secret", forbidden)
    rig.nobody = "this is a cron job"
    directive = rig.gate(tool_name="gcloud", args=deploy(), tool_call_id="c")
    assert directive["action"] == "block" and "Nothing was sent or changed" in directive["message"]
    assert access._GCLOUD_APPROVED == {}


# --- a command that asked on its card -------------------------------------------------------------

def test_a_carded_command_runs_after_its_card_once_and_only_as_it_showed(rig):
    args = deploy()
    directive, result = rig.gcloud(args)
    assert directive["action"] == "approve" and result["ok"] is True and len(rig.ran) == 1
    assert "gcloud run deploy --quiet --project=my-proj svc" in directive["message"]
    again = json.loads(rig.handlers["gcloud"](args))   # the card was answered once
    assert again["ok"] is False and "did not pass its approval card" in again["error"] and len(rig.ran) == 1


def test_a_carded_command_changed_after_its_card_is_refused(rig):
    rig.gate(tool_name="gcloud", args=deploy(), tool_call_id="call-4")
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "call-4")
    result = json.loads(rig.handlers["gcloud"](deploy("--memory=8Gi")))
    assert result["ok"] is False and "changed after its approval card" in result["error"] and rig.ran == []


def test_a_carded_command_survives_hermes_coercing_its_arguments(rig):
    """The hook sees the arguments as the model wrote them, the handler after Hermes coerces their types."""
    raw = {**deploy(), "timeout": "60"}
    rig.gate(tool_name="gcloud", args=raw, tool_call_id="call-6")
    rig.monkeypatch.setattr(plugin, "_call_id", lambda: "call-6")
    assert json.loads(rig.handlers["gcloud"]({**raw, "timeout": 60}))["ok"] is True and len(rig.ran) == 1


def test_a_command_with_no_card_at_all_is_refused_with_a_person_present(rig):
    result = json.loads(rig.handlers["gcloud"](deploy()))
    assert result["ok"] is False and "did not pass its approval card" in result["error"] and rig.ran == []


def test_a_denied_card_runs_nothing(rig):
    directive, result = rig.call("gcloud", deploy(), approve=False)
    assert directive["action"] == "approve" and result is None and rig.ran == []


# --- ways around the tool -------------------------------------------------------------------------

@pytest.mark.parametrize("tool, args", [
    ("read_file", {"path": "~/.hermes/profiles/assistant/google-access/head.json"}),
    ("read_file", {"path": "/h/profiles/assistant/google-access//uses.jsonl"}),
    ("search_files", {"path": "/h/profiles/assistant/google-access/mandates", "pattern": "id"}),
    ("patch", {"path": "/h/profiles/assistant/google-access/mandates.jsonl", "old_string": "a"}),
    ("write_file", {"path": "x", "content": "secret get GCLOUD_MANDATE_KEY_ASSISTANT"}),
    ("terminal", {"command": "cat ~/.hermes/profiles/assistant/google-access/uses.jsonl"}),
    ("terminal", {"command": "security find-generic-password -s GCLOUD_MANDATE_KEY_ASSISTANT"}),
    ("terminal", {"command": "ls /h/profiles/assistant/GOOGLE-ACCESS/Head.json"}),
    ("terminal", {"command": "secret get gcloud_mandate_key_assistant -p hermes"}),
])
def test_the_mandate_state_and_key_are_off_limits_to_file_and_terminal_calls(tool, args):
    assert access.bypass(tool, args) == access.BYPASS_MESSAGE


def test_a_link_to_the_mandate_state_does_not_hide_it(tmp_path):
    state = tmp_path / "home" / "google-access"
    state.mkdir(parents=True)
    (state / "head.json").write_text("{}")
    (tmp_path / "short").symlink_to(state)
    assert access.bypass("read_file", {"path": str(tmp_path / "short" / "head.json")}) == access.BYPASS_MESSAGE


def test_the_plugin_source_and_its_tests_stay_readable():
    for name in ("gcloud_mandate.py", "access.py", "tests/test_gcloud_mandate.py"):
        assert access.bypass("read_file", {"path": f"/repo/hermes/plugins/google-access/{name}"}) is None
    assert access.bypass("read_file", {"path": "/repo/hermes/docs/decisions/gcloud-mandates.md"}) is None


# --- against the installed SDK's own tree ---------------------------------------------------------

@pytest.fixture
def real_tree(monkeypatch):
    """The installed SDK's command tree, standing in for the stub one; skips without the SDK."""
    binary = access.shutil.which("gcloud")
    if not binary:
        pytest.skip("gcloud not installed")
    path = Path(binary).resolve().parent.parent / access.GCLOUD_TREE
    if not path.is_file():
        pytest.skip("no static command tree in this SDK")
    real = access._load_tree(str(path), path.stat().st_mtime_ns)
    monkeypatch.setattr(access, "_command_tree", lambda: real)
    return real


def declared(real, path):
    node = real
    for word in path:
        node = node["commands"][word]
    return node["flags"]


REAL_PATHS = [["run", "deploy"], ["functions", "deploy"], ["run", "services", "update"],
              ["compute", "instances", "create"], ["sql", "users", "create"]]


def classified_by_rules(path, flag):
    """What a flag is, from the rules alone (each flag lands in exactly one class)."""
    if not mandate.FLAG_NAME.fullmatch(flag):
        return "malformed"
    if flag in access.GCLOUD_FORBIDDEN_FLAGS:
        return "forbidden"
    if mandate.never_flag(flag):
        return "family"
    if access.gcloud_call({"command": path, "project": PROJECT, "args": [flag]}).writes_file:
        return "writes a file"
    return "listable"


def classified_by_terms(path, flag):
    """What a flag is, from what `terms` does with it."""
    try:
        mandate.terms(**{**GOOD, "commands": [path], "flags": [flag]})
    except access.AccessError:
        return "forbidden"
    except mandate.MandateError as exc:
        text = str(exc)
        for kind, marker in (("malformed", "flags is a list"), ("writes a file", "writes a local file"),
                             ("family", "names a local path or source"), ("family", "changes access, identity")):
            if marker in text:
                return kind
        return f"unexpected refusal: {text}"
    return "listable"


@pytest.mark.parametrize("path", REAL_PATHS, ids=" ".join)
def test_every_flag_the_real_tree_declares_is_in_exactly_one_class_and_create_agrees(real_tree, path):
    """No flag slips between the families and the allowlist: each flag the tree declares is malformed,
    forbidden, in a never-covered family, a file-writing flag or listable, and `terms` treats it so."""
    flags = list(declared(real_tree, path))
    expected = {flag: classified_by_rules(path, flag) for flag in flags}
    actual = {flag: classified_by_terms(path, flag) for flag in flags}
    counts = {"expected": dict(Counter(expected.values())), "actual": dict(Counter(actual.values()))}
    assert actual == expected, (path, counts, {f: (expected[f], actual[f]) for f in flags if actual[f] != expected[f]})
    assert sum(counts["actual"].values()) == len(flags), (path, counts)
    assert counts["actual"].get("family") and counts["actual"].get("listable"), (path, counts)
    assert not {"malformed", "forbidden"} & set(counts["actual"]), (path, counts)


# Flags a review named, and the ones this tree no longer declares for the path (none today; a flag
# the SDK drops is named here with the reason, not skipped).
NOT_DECLARED = {}
REVIEWED = {
    ("functions", "deploy"): ["--ingress-settings", "--run-service-account", "--build-service-account",
                              "--security-level", "--service-account", "--env-vars-file", "--source",
                              "--ignore-file", "--set-secrets", "--vpc-connector", "--network", "--subnet",
                              "--kms-key", "--direct-vpc-egress", "--trigger-service-account"],
    ("run", "deploy"): ["--breakglass", "--clear-network", "--key", "--ingress", "--service-account",
                        "--env-vars-file", "--source", "--set-secrets", "--vpc-connector", "--network",
                        "--subnet", "--add-volume", "--allow-unauthenticated", "--binary-authorization",
                        "--add-cloudsql-instances", "--add-custom-audiences", "--iap", "--vpc-egress",
                        "--namespace"],
    ("run", "services", "update"): ["--breakglass", "--clear-network", "--key", "--ingress", "--iap",
                                    "--invoker-iam-check", "--service-account", "--env-vars-file",
                                    "--set-secrets", "--vpc-connector", "--network", "--subnet",
                                    "--add-volume", "--binary-authorization", "--namespace"],
    ("compute", "instances", "create"): ["--image-project", "--scopes", "--metadata", "--service-account",
                                         "--network", "--subnet", "--no-address", "--address", "--no-scopes"],
    ("sql", "users", "create"): ["--password"],
}


@pytest.mark.parametrize("path, flags", [pytest.param(list(path), flags, id=" ".join(path))
                                         for path, flags in REVIEWED.items()])
def test_the_flags_the_review_named_are_refused_at_create_where_the_tree_declares_them(real_tree, path, flags):
    known = declared(real_tree, path)
    assert [flag for flag in flags if flag not in known] == NOT_DECLARED.get(tuple(path), []), path
    for flag in flags:
        if flag in known:
            with pytest.raises(mandate.MandateError, match="always asks on a card"):
                mandate.terms(**{**GOOD, "commands": [path], "flags": [flag]})
    assert mandate.never_flag("--no-iap") and mandate.never_flag("--no-require-ssl")


def test_the_flags_an_ordinary_deploy_needs_can_be_listed(real_tree):
    t = mandate.terms(**{**GOOD, "commands": [["run", "deploy"]], "flags": ["--image", "--region", "--memory",
                                                                          "--format", "--no-traffic"]})
    assert t["flags"] == ["--image", "--region", "--memory", "--format", "--no-traffic"]
    t = mandate.terms(**{**GOOD, "commands": [["functions", "deploy"]], "flags": ["--runtime", "--region",
                                                                                "--trigger-http"]})
    assert t["commands"] == [["functions", "deploy"]]


@pytest.mark.parametrize("path", [["storage", "rm"], ["compute", "instances", "set-service-account"],
                                  ["run", "services", "proxy"], ["storage", "cp"], ["sql", "backups", "restore"],
                                  ["compute", "instances", "stop"], ["compute", "instances", "add-metadata"],
                                  ["compute", "firewall-rules", "create"]], ids=" ".join)
def test_the_real_tree_paths_the_review_named_are_refused_at_create(real_tree, path):
    with pytest.raises(mandate.MandateError, match="always asks on a card"):
        mandate.terms(**{**GOOD, "commands": [path], "flags": []})
