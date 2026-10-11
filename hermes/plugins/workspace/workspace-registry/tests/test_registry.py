"""Tests for the registry engine and the wsreg CLI. Run: python3 -m unittest discover -s <this dir>"""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]


def _load(name, path):
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


R = _load("hermes_workspace_registry_engine", HERE / "registry.py")
CLI = _load("wsreg_under_test", HERE / "wsreg")


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "Workspaces"
        (self.root / "Projects" / "Acme").mkdir(parents=True)
        self.ghq = Path(self._tmp.name) / "ghq"
        peer_patch = mock.patch.object(R, "PEER_CHECKS", Path(self._tmp.name) / "peer_checks.py")
        peer_patch.start()
        self.addCleanup(peer_patch.stop)
        self._env = mock.patch.dict(os.environ, {"GHQ_ROOT": str(self.ghq)}, clear=False)
        self._env.start()
        os.environ.pop("WSREG_DIR", None)
        R.init(self.root)
        self.run_ok(action="project_set", id="Org", fields={"canonical_name": "Org Inc", "kind": "org"})
        self.run_ok(action="project_set", id="Acme", fields={"canonical_name": "Acme", "organization_id": "Org"})
        self.run_ok(action="person_set", id="ann", fields={"display_name": "Ann Lee", "timezone": "Asia/Tokyo"})

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def run_ok(self, **args):
        return R.run(args, root=self.root)

    def csv(self, name):
        return (self.root / ".registry" / f"{name}.csv").read_text(encoding="utf-8")

    def validate(self):
        return R.run({"action": "validate", "peers": False}, root=self.root)


class StorageTest(Base):
    def test_init_writes_every_header_and_refuses_twice(self):
        self.assertEqual(sorted(p.stem for p in (self.root / ".registry").glob("*.csv")), sorted(R.TABLES))
        with self.assertRaises(R.RegistryError):
            R.init(self.root)

    def test_rows_are_sorted_and_booleans_readable(self):
        self.run_ok(action="person_set", id="bob", fields={"display_name": "Bob"})
        text = self.csv("person_aliases")
        self.assertEqual(text.splitlines()[0], "person_id,alias,is_primary")
        self.assertLess(text.index("ann,"), text.index("bob,"))
        self.assertIn("Ann Lee,true", text)

    def test_missing_directory_is_an_error(self):
        with self.assertRaises(R.RegistryError):
            R.run({"action": "persons"}, root=Path(self._tmp.name) / "nowhere")

    def test_wsreg_dir_env_moves_only_the_data(self):
        other = Path(self._tmp.name) / "staging"
        with mock.patch.dict(os.environ, {"WSREG_DIR": str(other)}):
            R.init(self.root)
            self.assertEqual(R.run({"action": "persons"}, root=self.root)["persons"], [])
        self.assertEqual(len(self.run_ok(action="persons")["persons"]), 1)


class ValidationTest(Base):
    def edit(self, name, text):
        (self.root / ".registry" / f"{name}.csv").write_text(text, encoding="utf-8")

    def test_clean_registry_is_valid(self):
        out = self.validate()
        self.assertTrue(out["ok"], out)

    def test_hand_edit_errors_are_reported(self):
        self.edit("persons", "id,display_name,kind,status,review_status,residence_country,preferred_language,"
                  "preferred_contact_channel,timezone\nAnn,Ann,robot,active,confirmed,jp,,pager,Mars/Base\n")
        errs = "\n".join(self.validate()["errors"])
        for needle in ("not a bare lowercase slug", "kind 'robot'", "residence_country 'jp'",
                       "preferred_contact_channel 'pager'", "not an IANA name", "unknown person 'ann'"):
            self.assertIn(needle, errs)

    def test_unknown_column_and_duplicate(self):
        self.edit("tag_axes", "axis,label,extra\nstage,Stage,x\nstage,Again,y\n")
        errs = "\n".join(self.validate()["errors"])
        self.assertIn("unknown column(s) extra", errs)
        self.assertIn("duplicate tag_axes row", errs)

    def test_organization_rules(self):
        with self.assertRaisesRegex(R.RegistryError, "not kind=org"):
            self.run_ok(action="project_set", id="Org", fields={"organization_id": "Acme"})
        with self.assertRaisesRegex(R.RegistryError, "must stay kind=org"):
            self.run_ok(action="project_set", id="Org", fields={"kind": "client"})

    def test_self_organization_rejected(self):
        with self.assertRaisesRegex(R.RegistryError, "its own organization"):
            self.run_ok(action="project_set", id="Org", fields={"organization_id": "Org"})

    def test_warnings_for_unregistered_directory_and_axis(self):
        (self.root / "Projects" / "Stray").mkdir()
        self.run_ok(action="add", project="Acme", facet="tag", axis="stage", value="mvp")
        warns = "\n".join(self.validate()["warnings"])
        self.assertIn("Projects/Stray has no registry row", warns)
        self.assertIn("axis 'stage' has no row in tag_axes.csv", warns)

    def test_existing_error_does_not_block_unrelated_write(self):
        self.edit("project_links", "project_id,kind,url,label\nGhost,docs,https://x,\n")
        out = self.run_ok(action="add", person="ann", facet="language", value="JA", primary=True)
        self.assertTrue(out["ok"])
        self.assertIn("validation error", out["warnings"][0])
        self.assertIn("ann,ja,,true", self.csv("person_languages"))

    def test_invalid_write_is_rejected_and_nothing_written(self):
        before = self.csv("persons")
        with self.assertRaisesRegex(R.RegistryError, "change rejected"):
            self.run_ok(action="person_set", id="ann", fields={"kind": "robot"})
        self.assertEqual(self.csv("persons"), before)

class HandEditSafetyTest(Base):
    def path(self, name):
        return self.root / ".registry" / f"{name}.csv"

    def test_extra_cells_block_every_write_and_keep_the_file(self):
        with self.path("person_notes").open("a", encoding="utf-8") as f:
            f.write("ann,2026-01-01,met at cafe, Tokyo\n")
        before = self.path("person_notes").read_text(encoding="utf-8")
        with self.assertRaisesRegex(R.RegistryError, "structural errors"):
            self.run_ok(action="add", person="ann", facet="note", value="x")
        self.assertEqual(self.path("person_notes").read_text(encoding="utf-8"), before)
        self.assertIn("more cells than columns", "\n".join(self.validate()["errors"]))

    def test_header_typo_blocks_writes(self):
        text = self.path("persons").read_text(encoding="utf-8").replace("id,display_name", "id, display_name", 1)
        self.path("persons").write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(R.RegistryError, "structural errors"):
            self.run_ok(action="person_set", id="ann", fields={"timezone": "Asia/Tokyo"})
        self.assertIn(" display_name", self.path("persons").read_text(encoding="utf-8"))

    def test_unreadable_file_is_reported_not_raised(self):
        self.path("project_links").write_bytes("project_id,kind,url,label\nAcme,docs,\x83\x65,\n".encode("latin-1"))
        errs = "\n".join(self.validate()["errors"])
        self.assertIn("project_links.csv: unreadable", errs)
        self.assertIn("warnings", self.run_ok(action="projects"))

    def test_odd_boolean_word_does_not_break_reads(self):
        text = self.path("project_aliases").read_text(encoding="utf-8").replace("Acme,true", "Acme,y")
        self.path("project_aliases").write_text(text, encoding="utf-8")
        self.assertEqual(len(self.run_ok(action="projects")["projects"]), 2)
        self.assertIn("is_primary 'y' is not true/false", "\n".join(self.validate()["errors"]))


class PeopleTest(Base):
    def test_create_needs_display_name_and_adds_primary_alias(self):
        with self.assertRaisesRegex(R.RegistryError, "display_name"):
            self.run_ok(action="person_set", id="x", fields={})
        p = self.run_ok(action="person", id="ann")["person"]
        self.assertEqual(p["review_status"], "needs_review")
        self.assertEqual(p["aliases"], [{"alias": "Ann Lee", "is_primary": True}])

    def test_partial_update_and_clear(self):
        self.run_ok(action="person_set", id="ann", fields={"residence_country": "my", "timezone": ""})
        p = self.run_ok(action="person", id="ann")["person"]
        self.assertEqual((p["residence_country"], p["timezone"], p["display_name"]), ("MY", None, "Ann Lee"))

    def test_primary_moves(self):
        self.run_ok(action="add", person="ann", facet="alias", value="Annie", primary=True)
        aliases = self.run_ok(action="person", id="ann")["person"]["aliases"]
        self.assertEqual({a["alias"]: a["is_primary"] for a in aliases}, {"Ann Lee": False, "Annie": True})

    def test_whois_by_handle_alias_and_substring(self):
        self.run_ok(action="add", person="ann", facet="contact", channel="telegram", value="@ann_tg", primary=True)
        self.assertEqual([m["id"] for m in self.run_ok(action="whois", query="https://t.me/Ann_TG")["matches"]], ["ann"])
        self.assertEqual([m["id"] for m in self.run_ok(action="whois", query="ann lee")["matches"]], ["ann"])
        self.assertEqual([m["id"] for m in self.run_ok(action="whois", query="lee")["matches"]], ["ann"])
        self.assertEqual(self.run_ok(action="whois", query="nobody")["matches"], [])

    def test_notes_keep_order_and_remove(self):
        self.run_ok(action="add", person="ann", facet="note", value="second", date="2026-01-02")
        self.run_ok(action="add", person="ann", facet="note", value="first?", date="2026-01-01")
        self.assertEqual([n["text"] for n in self.run_ok(action="person", id="ann")["person"]["notes"]],
                         ["second", "first?"])
        self.run_ok(action="remove", person="ann", facet="note", value="second")
        with self.assertRaisesRegex(R.RegistryError, "no note"):
            self.run_ok(action="remove", person="ann", facet="note", value="second")

    def test_facet_target_checks(self):
        with self.assertRaisesRegex(R.RegistryError, "exactly one"):
            self.run_ok(action="add", facet="alias", value="x")
        with self.assertRaisesRegex(R.RegistryError, "does not apply"):
            self.run_ok(action="add", project="Acme", facet="contact", value="x")


class ProjectsTest(Base):
    def test_project_view_and_org_children(self):
        acme = self.run_ok(action="project", id="Acme")["project"]
        self.assertEqual(acme["dir_path"], str(self.root / "Projects" / "Acme"))
        self.assertEqual(acme["slug"], "acme")
        org = self.run_ok(action="project", id="Org")["project"]
        self.assertIsNone(org["dir_path"])
        self.assertEqual(org["projects"], ["Acme"])
        self.assertEqual([p["id"] for p in self.run_ok(action="projects", organization="Org")["projects"]], ["Acme"])

    def test_members_lists_replace(self):
        self.run_ok(action="member_set", project="Acme", person="ann",
                    fields={"roles": ["dev", "pm"], "can_merge": True, "notes": ["n1"]})
        self.run_ok(action="member_set", project="Acme", person="ann", fields={"roles": ["pm"]})
        m = self.run_ok(action="members", project="Acme")["memberships"][0]
        self.assertEqual((m["roles"], m["can_merge"], m["notes"], m["person_name"]), (["pm"], True, ["n1"], "Ann Lee"))
        self.assertEqual([p["id"] for p in self.run_ok(action="persons", project="Acme")["persons"]], ["ann"])
        self.run_ok(action="member_rm", project="Acme", person="ann")
        self.assertEqual(self.csv("membership_notes").strip(), "project_id,person_id,text")

    def test_member_needs_existing_person(self):
        with self.assertRaisesRegex(R.RegistryError, "no person 'zed'"):
            self.run_ok(action="member_set", project="Acme", person="zed")

    def test_repo_paths_are_derived_and_link_repo(self):
        out = self.run_ok(action="repo_set", project="Acme", name="app",
                          fields={"owner": "acme", "ghq_path": str(self.ghq / "github.com" / "acme" / "app")})
        repo = out["repo"]
        self.assertEqual(repo["url"], "https://github.com/acme/app")
        self.assertEqual(repo["link_path"], str(self.root / "Projects" / "Acme" / "github" / "app"))
        self.assertNotIn(str(self.ghq), self.csv("repos"))  # default path is not stored
        self.assertEqual(self.run_ok(action="link_repo", project="Acme", name="app")["status"], "missing")
        clone = self.ghq / "github.com" / "acme" / "app"
        clone.mkdir(parents=True)
        (clone / "AGENTS.md").write_text("x")
        self.assertEqual(self.run_ok(action="link_repo", project="Acme", name="app")["status"], "linked")
        self.assertTrue((self.root / "Projects" / "Acme" / "github" / "app").is_symlink())
        self.assertEqual(self.run_ok(action="link_repo", project="Acme", name="app")["note"], "symlink already correct")
        self.assertTrue(self.run_ok(action="repos", project="Acme")["repos"][0]["has_agents_md"])

    def test_nonstandard_ghq_path_is_kept(self):
        self.run_ok(action="repo_set", project="Acme", name="odd", fields={"owner": "o", "ghq_path": "/opt/src/odd"})
        self.assertEqual(self.run_ok(action="repos")["repos"][0]["ghq_path"], "/opt/src/odd")

    def test_rename_project_rewrites_references(self):
        self.run_ok(action="member_set", project="Acme", person="ann", fields={"roles": ["dev"]})
        out = self.run_ok(action="rename", project="Org", new_id="Org2")
        self.assertIsNone(out["note"])
        self.assertEqual(self.run_ok(action="project", id="Acme")["project"]["organization_id"], "Org2")
        out = self.run_ok(action="rename", project="Acme", new_id="Acme2")
        self.assertIn("was not moved", out["note"])
        self.assertEqual(self.run_ok(action="members", project="Acme2")["memberships"][0]["roles"], ["dev"])

    def test_repo_names_cannot_escape_the_group(self):
        for bad in ("acme/app", "..", "../x"):
            with self.assertRaisesRegex(R.RegistryError, "change rejected"):
                self.run_ok(action="repo_set", project="Acme", name=bad, fields={"owner": "acme"})
        with self.assertRaisesRegex(R.RegistryError, "change rejected"):
            self.run_ok(action="repo_set", project="Acme", name="app", fields={"owner": "a/b"})
        with self.assertRaisesRegex(R.RegistryError, "change rejected"):
            self.run_ok(action="repo_set", project="Acme", name="app", fields={"ghq_path": "relative/app"})

    def test_link_repo_never_replaces_a_real_directory(self):
        self.run_ok(action="repo_set", project="Acme", name="app", fields={"owner": "acme"})
        (self.ghq / "github.com" / "acme" / "app").mkdir(parents=True)
        (self.root / "Projects" / "Acme" / "github" / "app").mkdir(parents=True)
        with self.assertRaisesRegex(R.RegistryError, "not the expected symlink"):
            self.run_ok(action="link_repo", project="Acme", name="app")
        self.assertTrue((self.root / "Projects" / "Acme" / "github" / "app").is_dir())

    def test_rename_person_rewrites_every_table(self):
        self.run_ok(action="add", person="ann", facet="contact", channel="github", value="annl")
        self.run_ok(action="add", person="ann", facet="note", value="hi")
        self.run_ok(action="member_set", project="Acme", person="ann", fields={"areas": ["web"]})
        out = self.run_ok(action="rename", person="ann", new_id="ann_lee")
        self.assertIsNone(out["note"])
        p = self.run_ok(action="person", id="ann_lee")["person"]
        self.assertEqual((len(p["aliases"]), len(p["contacts"]), len(p["notes"]), p["memberships"][0]["areas"]),
                         (1, 1, 1, ["web"]))
        self.assertTrue(self.validate()["ok"])

    def test_group_create_makes_dirs_agents_md_and_row(self):
        out = self.run_ok(action="group_create", id="Beta",
                          fields={"canonical_name": "Beta Co", "organization_id": "Org", "summary": "Beta app"})
        base = self.root / "Projects" / "Beta"
        self.assertEqual(sorted(out["made"]), ["AGENTS.md", "data/", "docs/", "github/"])
        self.assertTrue(all((base / d).is_dir() for d in ("github", "docs", "data")))
        text = (base / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Beta\n"))
        self.assertIn("Beta app", text)
        p = self.run_ok(action="project", id="Beta")["project"]
        self.assertEqual((p["dir_path"], p["organization_id"], p["slug"]), (str(base), "Org", "beta-co"))

    def test_group_create_keeps_existing_files(self):
        (self.root / "Projects" / "Acme" / "AGENTS.md").write_text("mine", encoding="utf-8")
        out = self.run_ok(action="group_create", id="Acme")
        self.assertFalse(out["created"])
        self.assertNotIn("AGENTS.md", out["made"])
        self.assertEqual((self.root / "Projects" / "Acme" / "AGENTS.md").read_text(encoding="utf-8"), "mine")

    def test_group_create_invalid_row_touches_nothing(self):
        with self.assertRaisesRegex(R.RegistryError, "not kind=org"):
            self.run_ok(action="group_create", id="Gamma", fields={"organization_id": "Acme"})
        with self.assertRaisesRegex(R.RegistryError, "has no Projects/ directory"):
            self.run_ok(action="group_create", id="Delta", fields={"kind": "org"})
        with self.assertRaisesRegex(R.RegistryError, "change rejected"):
            self.run_ok(action="group_create", id="../x")
        for name in ("Gamma", "Delta", "x"):
            self.assertFalse((self.root / "Projects" / name).exists(), name)
        self.assertFalse((self.root / "x").exists())
        self.assertEqual({p["id"] for p in self.run_ok(action="projects")["projects"]}, {"Acme", "Org"})

    def test_review_lists_needs_review(self):
        self.assertEqual(self.run_ok(action="review"), {"persons": ["ann"], "projects": ["Acme", "Org"], "repos": []})


class CliTest(Base):
    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = CLI.main(["--root", str(self.root), *argv])
        return code, out.getvalue(), err.getvalue()

    def test_read_prints_envelope(self):
        code, out, _ = self.cli("projects", "--json")
        env = json.loads(out)
        self.assertEqual((code, env["contract_version"], env["skill"]), (0, 1, "registry"))
        self.assertEqual({p["id"] for p in env["data"]["projects"]}, {"Org", "Acme"})

    def test_wslink_style_repo_set(self):
        code, _, _ = self.cli("repo-set", "--project", "Acme", "--name", "app", "--owner", "acme",
                              "--ghq-path", "/x/app", "--has-agents-md")
        self.assertEqual(code, 0)
        code, _, _ = self.cli("repo-set", "--project", "Acme", "--name", "app", "--status", "declared")
        env = json.loads(self.cli("repos", "--json", "--project", "Acme")[1])
        self.assertEqual((env["data"]["repos"][0]["ghq_path"], env["data"]["repos"][0]["status"]), ("/x/app", "declared"))
        self.assertEqual(self.cli("repo-rm", "--project", "Acme", "--name", "app")[0], 0)

    def test_member_set_repeated_flags(self):
        self.cli("member-set", "--project", "Acme", "--person", "ann", "--role", "a", "--role", "b", "--can-deploy")
        m = json.loads(self.cli("members")[1])["data"]["memberships"][0]
        self.assertEqual((m["roles"], m["can_deploy"]), (["a", "b"], True))

    def test_errors_exit_one(self):
        code, _, err = self.cli("person", "--id", "nobody")
        self.assertEqual(code, 1)
        self.assertIn("no person 'nobody'", err)
        code, out, _ = self.cli("validate")
        self.assertEqual(code, 0)
        self.assertIn("passed", out)

    def test_project_set_organization_flag(self):
        self.cli("project-set", "--id", "Beta", "--canonical-name", "Beta Co", "--organization", "Org")
        self.assertEqual(self.run_ok(action="project", id="Beta")["project"]["organization_id"], "Org")


if __name__ == "__main__":
    unittest.main()
