from __future__ import annotations

import importlib.util
import shlex
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch


def load_plugin() -> ModuleType:
    plugin_path = Path(__file__).resolve().parents[1] / "__init__.py"
    spec = importlib.util.spec_from_file_location("skill_topology_plugin", plugin_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load plugin from {plugin_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeContext:
    def __init__(self) -> None:
        self.middleware: dict[str, Any] = {}
        self.hooks: dict[str, Any] = {}

    def register_middleware(self, kind: str, callback: Any) -> None:
        self.middleware[kind] = callback

    def register_hook(self, kind: str, callback: Any) -> None:
        self.hooks[kind] = callback


class SkillTopologyPluginTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plugin = load_plugin()

    def test_no_tool_request_middleware_rewrites_creates(self) -> None:
        """Placement is skills.create_dir's job; a category rewrite would nest learned/learned/."""
        context = FakeContext()

        self.plugin.register(context)

        self.assertNotIn("tool_request", context.middleware)
        self.assertFalse(hasattr(self.plugin, "_route_skill_create"))
        self.assertIs(context.hooks["pre_tool_call"], self.plugin._guard_managed_skill_writes)

    def test_learned_category_name_is_the_create_dir_leaf(self) -> None:
        self.assertEqual(self.plugin.LEARNED_CATEGORY, "learned")


class ManagedSkillWriteGuardTest(unittest.TestCase):
    """Maintainer-owned skill files are read-only at runtime."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.plugin = load_plugin()
        temporary = tempfile.TemporaryDirectory(prefix="skill-topology-test-")
        cls.addClassCleanup(temporary.cleanup)
        cls.fixture_root = Path(temporary.name).resolve()
        cls.plugin.MANAGED_ROOT = cls.fixture_root / "hermes"
        cls.managed = str(
            cls.plugin.MANAGED_ROOT
            / "profiles/image-creator/skills/image-creator-pipeline/create/emoji/scripts/text-emoji.sh"
        )
        cls.learned = str(cls.plugin.MANAGED_ROOT / "profiles/image-creator/skills/learned/x/SKILL.md")
        cls.skills = cls.plugin.MANAGED_ROOT / "profiles/image-creator/skills"
        cls.skills.mkdir(parents=True)
        cls.alias = cls.fixture_root / "home-alias"
        cls.alias.symlink_to(cls.plugin.MANAGED_ROOT, target_is_directory=True)
        cls.script = str(cls.skills / "image-creator-pipeline/create/emoji/scripts/propose.py")

    def guard(self, tool_name: str, **args: Any) -> Any:
        return self.plugin._guard_managed_skill_writes(tool_name=tool_name, args=args)

    def test_write_file_into_managed_root_is_blocked(self) -> None:
        result = self.guard("write_file", path=self.managed, content="x")
        self.assertEqual(result["action"], "block")

    def test_patch_into_managed_root_is_blocked(self) -> None:
        result = self.guard("patch", path=self.managed, old_string="a", new_string="b")
        self.assertEqual(result["action"], "block")

    def test_v4a_patch_naming_a_managed_file_is_blocked(self) -> None:
        result = self.guard("patch", mode="v4a", patch=f"*** Begin Patch\n*** Update File: {self.managed}\n")
        self.assertEqual(result["action"], "block")

    def test_learned_stays_writable(self) -> None:
        self.assertIsNone(self.guard("write_file", path=self.learned, content="x"))

    def test_deliverables_stay_writable(self) -> None:
        self.assertIsNone(self.guard("write_file", path="/tmp/emoji/items.tsv", content="x"))

    def test_symlinked_hermes_home_path_resolves_to_managed(self) -> None:
        home = self.alias / "profiles/image-creator/skills/image-creator-pipeline/SKILL.md"
        self.assertEqual(self.guard("write_file", path=str(home), content="x")["action"], "block")

    def test_terminal_redirect_into_managed_root_is_blocked(self) -> None:
        result = self.guard("terminal", command=f"echo x > {self.managed}")
        self.assertEqual(result["action"], "block")

    def test_terminal_read_of_managed_file_is_allowed(self) -> None:
        self.assertIsNone(self.guard("terminal", command=f"bash {self.managed} items.tsv /tmp/out --platform slack"))

    def test_terminal_write_elsewhere_is_allowed(self) -> None:
        self.assertIsNone(self.guard("terminal", command="echo x > /tmp/out/finish.sh"))

    def test_script_argument_command_fragments_are_data(self) -> None:
        self.assertFalse(Path(self.script).exists())
        for fragment in ("mv", "cp", "rm", "chmod", "truncate", "tee", "sed"):
            with self.subTest(fragment=fragment):
                command = f"python {self.script} --out /tmp/lethe-{fragment}-no-voice/proposal-v1"
                self.assertIsNone(self.guard("terminal", command=command))
                self.assertEqual(self.guard("terminal", command=f"{command} > {self.managed}")["action"], "block")

    def test_literal_read_and_external_write_commands(self) -> None:
        commands = (
            f"cp {self.managed} /tmp/out",
            f"cp -- {self.managed} /tmp/out",
            f"cp -t /tmp/out {self.managed}",
            f"cp {self.managed} --target-directory=/tmp/out",
            f"sed 's/a/b/' {self.managed}",
            f"sed -n -e '1p' {self.managed}",
            f"cat < {self.managed} > /tmp/out",
            f"python {self.script} --out /tmp/out > /tmp/log 2>&1",
            f"echo {self.managed} | tee -a /tmp/out",
            f"rm -rf {self.learned}",
            "mv /tmp/in /tmp/out",
            "rm -rf /tmp/unrelated-output",
            "chmod +x /tmp/out",
            "truncate -s 0 /tmp/out",
            f"truncate --reference={self.managed} -s 0 /tmp/out",
            f"chmod --reference={self.managed} /tmp/out",
            f"sed -i '' 's/a/b/' {self.learned}",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNone(self.guard("terminal", command=command))

    def test_direct_mutations_remain_blocked(self) -> None:
        commands = (
            f"cp /tmp/input {self.managed}",
            f"cp -f -- /tmp/input {self.managed}",
            f"mv {self.managed} /tmp/out",
            f"mv /tmp/out {self.managed}",
            f"rm -f {self.managed}",
            f"chmod +x {self.managed}",
            f"chmod -R 755 {self.managed}",
            f"chmod -w {self.managed}",
            f"chmod -- -w {self.managed}",
            f"chmod --reference=/tmp/ref {self.managed}",
            f"chmod --reference /tmp/ref {self.managed}",
            f"truncate -s 0 {self.managed}",
            f"truncate --size=0 {self.managed}",
            f"tee {self.managed}",
            f"tee -a {self.managed}",
            f"sed -i '' 's/a/b/' {self.managed}",
            f"sed -i.bak 's/a/b/' {self.managed}",
            f"sed -i 's/a/b/' {self.managed}",
            f"sed --in-place=.bak -e 's/a/b/' {self.managed}",
            f"sed -ni 's/a/b/' {self.managed}",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(self.guard("terminal", command=command)["action"], "block")

    def test_target_directory_options(self) -> None:
        directory = str(Path(self.managed).parent)
        for executable in ("cp", "mv"):
            for option in (f"-t {directory}", f"-t{directory}",
                           f"--target-directory {directory}", f"--target-directory={directory}"):
                for arguments in (f"{option} /tmp/input", f"/tmp/input {option}"):
                    command = f"{executable} {arguments}"
                    with self.subTest(command=command):
                        self.assertEqual(self.guard("terminal", command=command)["action"], "block")

    def test_unknown_wrappers_and_subcommands_are_reference_gated(self) -> None:
        templates = (
            "git rm {target}", "git mv {target} /tmp/out", "echo {target} | xargs rm",
            "timeout 300 rm {target}", "nohup mv {target} /tmp/out", "time rm {target}",
            "nice -n10 cp /tmp/in {target}", "stdbuf -o0 tee {target}", "doas rm {target}",
            "timeout 300 /bin/rm {target}", "echo {target} | xargs /bin/rm",
        )
        for template in templates:
            with self.subTest(template=template):
                result = self.guard("terminal", command=template.format(target=self.managed))
                self.assertEqual(result["action"], "block")
                self.assertIn("Conservatively blocked", result["message"])
                self.assertIsNone(self.guard("terminal", command=template.format(target="/tmp/unrelated-file")))

    def test_wrapper_fallback_does_not_treat_data_as_mutators(self) -> None:
        for command in (f"echo 'rm' '{self.managed}'", f"printf '%s\\n' 'mv' '{self.managed}'",
                        f"ls rm '{self.managed}'", f"cat cp '{self.managed}'",
                        f"python {self.script} 'rm' --out /tmp/lethe-mv-no-voice",
                        f"custom-reader {self.managed} /tmp/lethe-mv-no-voice",
                        f"custom-reader {self.managed} 'rm /tmp/out'",
                        f"git show {self.managed}"):
            with self.subTest(command=command):
                self.assertIsNone(self.guard("terminal", command=command))

    def test_recursive_copy_protects_managed_containers_only(self) -> None:
        for option in ("-r", "-R", "-a", "--recursive", "--archive", "-rp", "-PR", "-av"):
            for target in (self.skills.parent, self.skills.parent.parent, self.plugin.MANAGED_ROOT):
                command = f"cp {option} /tmp/in {target}"
                with self.subTest(command=command):
                    self.assertEqual(self.guard("terminal", command=command)["action"], "block")
            self.assertIsNone(self.guard("terminal", command=f"cp {option} /tmp/in {self.plugin.MANAGED_ROOT}/plugins"))
            self.assertIsNone(self.guard("terminal", command=f"cp {option} /tmp/in /tmp/unrelated-output"))
        for command in (f"cp /tmp/in {self.plugin.MANAGED_ROOT}/profiles/notes.txt",
                        f"cp -t{self.plugin.MANAGED_ROOT}/profiles /tmp/in",
                        f"cp -- /tmp/in {self.plugin.MANAGED_ROOT}/profiles/notes.txt"):
            with self.subTest(command=command):
                self.assertIsNone(self.guard("terminal", command=command))
        for target in (self.skills.parent, self.skills.parent.parent):
            command = f"cp -rt {target} /tmp/in"
            self.assertEqual(self.guard("terminal", command=command)["action"], "block")
        self.assertIsNone(self.guard("terminal", command="cp -rt /tmp/unrelated-output /tmp/in"))

    def test_ambiguous_chmod_flags_are_reference_gated(self) -> None:
        for option in ("-Rw", "-R+x", "-Rf-w", "--unknown-mode"):
            with self.subTest(option=option):
                result = self.guard("terminal", command=f"chmod {option} {self.managed}")
                self.assertEqual(result["action"], "block")
                self.assertIn("Conservatively blocked", result["message"])
                self.assertIsNone(self.guard("terminal", command=f"chmod {option} /tmp/unrelated-file"))
        for mode in ("-R +x", "-Rv 755", "--recursive u=rw,go=r", "-R -w", "-- -w"):
            with self.subTest(mode=mode):
                self.assertEqual(self.guard("terminal", command=f"chmod {mode} {self.managed}")["action"], "block")
                self.assertIsNone(self.guard("terminal", command=f"chmod {mode} /tmp/unrelated-file"))

    def test_write_redirections_are_checked_independently_of_executable(self) -> None:
        for operator in (">>", ">", ">|", "2>", "&>", "&>>", "1>>", "<>", ">&"):
            for executable in ("echo x", f"python {self.script}", f"bash {self.managed}"):
                command = f"{executable} {operator}{self.managed}"
                with self.subTest(command=command):
                    self.assertEqual(self.guard("terminal", command=command)["action"], "block")
        self.assertEqual(self.guard("terminal", command=f">{self.managed} echo x")["action"], "block")

    def test_all_simple_commands_are_checked(self) -> None:
        for separator in (" && ", " || ", "; ", " | ", "\n", " & ", " |& "):
            for command in (f"python {self.script}{separator}rm {self.managed}",
                            f"rm {self.managed}{separator}echo complete"):
                with self.subTest(command=command):
                    self.assertEqual(self.guard("terminal", command=command)["action"], "block")
            self.assertIsNone(self.guard("terminal", command=f"cat {self.managed}{separator}echo complete"))

    def test_quoted_operators_and_command_words_are_data(self) -> None:
        for data in (f"rm {self.managed}", f"; cp /tmp/in {self.managed}",
                     f"> {self.managed}", f"&& mv {self.managed} /tmp/out",
                     f"\nchmod +x {self.managed}", f"$(rm {self.managed})",
                     f"`rm {self.managed}`", "|", "<", "2>"):
            with self.subTest(data=data):
                self.assertIsNone(self.guard("terminal", command=f"python {self.script} --label {shlex.quote(data)}"))
        self.assertIsNone(self.guard("terminal", command=f'echo "rm {self.managed}; > | &&"'))
        self.assertIsNone(self.guard("terminal", command=f"echo rm\\; {self.managed} \\> /tmp/out"))
        self.assertEqual(self.guard("terminal", command=f"'rm' '{self.managed}'")["action"], "block")

    def test_wrappers_preserve_command_identity(self) -> None:
        for wrapper in ("env VAR=value", "env -i -u UNUSED VAR=value", "command", "command -p",
                        "builtin", "sudo", "sudo -n -u root --", "sudo --user=root",
                        "env VAR=value command sudo -n"):
            with self.subTest(wrapper=wrapper):
                self.assertIsNone(self.guard("terminal", command=f"{wrapper} /usr/bin/python {self.script} --out /tmp/lethe-mv-no-voice/proposal-v1"))
                self.assertEqual(self.guard("terminal", command=f"{wrapper} /bin/rm {self.managed}")["action"], "block")
                self.assertEqual(self.guard("terminal", command=f"{wrapper} cp /tmp/in {self.managed}")["action"], "block")
        self.assertIsNone(self.guard("terminal", command=f"command -v rm {self.managed}"))
        self.assertEqual(self.guard("terminal", command=f"command -v rm > {self.managed}")["action"], "block")

    def test_explicit_working_directory_and_spaced_paths(self) -> None:
        relative = "image-creator-pipeline/create/emoji/file with spaces.txt"
        for key in ("cwd", "workdir"):
            for command in (f"rm '{relative}'", f"cp /tmp/in '{relative}'", f"echo x > '{relative}'"):
                with self.subTest(key=key, command=command):
                    self.assertEqual(self.guard("terminal", command=command, **{key: str(self.skills)})["action"], "block")
            self.assertIsNone(self.guard("terminal", command=f"cp '{relative}' /tmp/out", **{key: str(self.skills)}))
        managed = shlex.quote(str(Path(self.managed).parent / "file with spaces.txt"))
        self.assertEqual(self.guard("terminal", command=f"tee {managed}")["action"], "block")
        self.assertIsNone(self.guard("terminal", command=f"cp {managed} '/tmp/file with spaces.txt'"))

    def test_omitted_workdir_never_uses_the_plugin_process_cwd(self) -> None:
        with patch.object(self.plugin.os, "getcwd", side_effect=AssertionError("process cwd is not terminal cwd")):
            for command in ("rm relative-file", "cp /tmp/in relative-file", "mv relative-file /tmp/out",
                            "chmod +x relative-file", "tee relative-file", "echo x > relative-file",
                            "sed -i '' 's/a/b/' relative-file"):
                with self.subTest(command=command):
                    result = self.guard("terminal", command=command)
                    self.assertEqual(result["action"], "block")
                    self.assertIn("known terminal working directory", result["message"])
                    self.assertIsNone(self.guard("terminal", command=command, workdir="/tmp"))
                    self.assertEqual(self.guard("terminal", command=command, cwd=str(Path(self.managed).parent))["action"], "block")
            for command in ("ls relative-file", "sed -n '1p' relative-file", "python script.py --out relative-out",
                            "echo ';'", "rm /tmp/unrelated-file", f"cp {self.managed} /tmp/out"):
                with self.subTest(command=command):
                    self.assertIsNone(self.guard("terminal", command=command))

    def test_terminal_symlink_targets(self) -> None:
        alias = self.alias / Path(self.managed).relative_to(self.plugin.MANAGED_ROOT)
        for command in (f"rm {alias}", f"cp /tmp/in {alias}", f"echo x > {alias}"):
            with self.subTest(command=command):
                self.assertEqual(self.guard("terminal", command=command)["action"], "block")
        self.assertIsNone(self.guard("terminal", command=f"cp {alias} /tmp/out"))
        link = self.fixture_root / "target-link"
        link.symlink_to(self.managed)
        self.assertEqual(self.guard("terminal", command=f"tee {link}")["action"], "block")
        # cp into a directory can write through a child symlink.
        self.assertEqual(self.guard("terminal", command=f"cp /tmp/target-link {self.fixture_root}")["action"], "block")
        self.assertEqual(self.guard("terminal", command=f"cd /tmp && cp /tmp/target-link {self.fixture_root}")["action"], "block")

    def test_modes_and_sed_expressions_are_not_write_targets(self) -> None:
        cwd = str(Path(self.managed).parent)
        for command in ("chmod +x /tmp/out", "chmod -R 755 /tmp/out", "chmod -w /tmp/out",
                        "chmod --reference /tmp/ref /tmp/out", "chmod -- -w /tmp/out",
                        "sed -i '' 's/a/b/' /tmp/out", "sed -i.bak 's/a/b/' /tmp/out",
                        "sed --in-place -e 's/a/b/' /tmp/out", "truncate -s 0 /tmp/out"):
            with self.subTest(command=command):
                self.assertIsNone(self.guard("terminal", command=command, workdir=cwd))

    def test_literal_tilde_and_shell_expanded_home_are_distinct(self) -> None:
        with patch.dict("os.environ", {"HOME": str(self.alias)}):
            target = "~/profiles/image-creator/skills/image-creator-pipeline/SKILL.md"
            self.assertEqual(self.guard("terminal", command=f"rm {target}")["action"], "block")
            self.assertIsNone(self.guard("terminal", command=f"rm '{target}'", workdir="/tmp"))
            self.assertIsNone(self.guard("terminal", command=f'rm "{target}"', workdir="/tmp"))

    def test_script_options_are_data_after_the_script_name(self) -> None:
        for executable in ("python", "python3.11 -u", "python -X dev", "python -O", "bash", "bash -e"):
            command = f"{executable} {self.script} -c 'rm {self.managed}'"
            with self.subTest(command=command):
                self.assertIsNone(self.guard("terminal", command=command))
                self.assertEqual(self.guard("terminal", command=f"{command} > {self.managed}")["action"], "block")

    def test_unrelated_commands_are_left_to_terminal_policy(self) -> None:
        commands = (
            "python -c 'print(1)'", "python -O -c 'print(1)'", "python --version",
            "node -e 'console.log(1)'", "node --eval='console.log(1)'",
            "bash -lc 'pwd'", "eval 'echo ok'", "(pwd)",
            "git log $(git merge-base main HEAD)", "git log `git merge-base main HEAD`",
            "cd /tmp", "cd /tmp && ls", "cd /tmp && python -c 'print(1)'",
            "env -S 'python -c print(1)'", "sudo -D /tmp ls",
            "echo ';'", 'echo ";"', "echo '&&' '|' '>'", "cat <<EOF\nhello\nEOF",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNone(self.guard("terminal", command=command))

    def test_template_script_paths_and_read_operands_are_allowed(self) -> None:
        for script in ('"${HERMES_SKILL_DIR}/../../scripts/thing.py"',
                       '"$HERMES_SKILL_DIR/../../scripts/thing.py"',
                       '"${HOME}/.hermes/skills/example/scripts/thing.py"',
                       '"$HOME/.hermes/skills/example/scripts/thing.py"'):
            for executable in ("python", "python -u", "env VAR=value /usr/bin/python", "bash --norc"):
                command = f"{executable} {script} --out /tmp/lethe-mv-no-voice"
                with self.subTest(command=command):
                    self.assertIsNone(self.guard("terminal", command=command))
                    self.assertEqual(self.guard("terminal", command=f"{command} > {self.managed}")["action"], "block")
                    self.assertEqual(self.guard("terminal", command=f"{command}; cp /tmp/in {self.managed}")["action"], "block")
        for command in ('ls "${HERMES_SKILL_DIR}"', 'sed -nE "1p" "${HERMES_SKILL_DIR}/SKILL.md"',
                        'sed -e "$EXPRESSION" "$FILE"', 'sed "$EXPRESSION" "$FILE"',
                        f'sed -e "$EXPRESSION" "{self.managed}"'):
            with self.subTest(command=command):
                self.assertIsNone(self.guard("terminal", command=command))

    def test_documented_runtime_command_paths_are_allowed(self) -> None:
        commands = (
            '${HERMES_SKILL_DIR}/scripts/text-emoji.sh /abs/input /abs/out',
            '"${HERMES_SKILL_DIR}/scripts/text-emoji.sh" /abs/input /abs/out',
            '$HERMES_SKILL_DIR/scripts/text-emoji.sh /abs/input /abs/out',
            '"$HERMES_SKILL_DIR/scripts/text-emoji.sh" /abs/input /abs/out',
            '"$(ghq root)/github.com/NousResearch/hermes-agent/venv/bin/python" '
            '"${HERMES_SKILL_DIR}/../../scripts/speech-media.py" analyze /tmp/a.wav',
            '$(ghq root)/github.com/NousResearch/hermes-agent/venv/bin/python '
            '"${HERMES_SKILL_DIR}/../../scripts/speech-media.py" analyze /tmp/a.wav',
            '"${HOME}/bin/python" "${HERMES_SKILL_DIR}/scripts/thing.py" --out /tmp/lethe-mv-no-voice',
            '$HOME/bin/python "${HERMES_SKILL_DIR}/scripts/thing.py" --out /tmp/lethe-mv-no-voice',
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNone(self.guard("terminal", command=command))
                self.assertEqual(self.guard("terminal", command=f"{command} > {self.managed}")["action"], "block")

    def test_runtime_command_fragments_remain_unexpanded_and_dynamic(self) -> None:
        with patch("subprocess.Popen", side_effect=AssertionError("guard must not execute commands")), \
                patch.object(self.plugin.os, "system", side_effect=AssertionError("guard must not execute commands")):
            for prefix in ("${HERMES_SKILL_DIR}", "$HERMES_SKILL_DIR", "${HOME}", "$HOME", "$(ghq root)"):
                path = prefix + "/bin/python"
                with self.subTest(path=path):
                    tokens = self.plugin._shell_tokens(f'"{path}" "${{HERMES_SKILL_DIR}}/scripts/thing.py"')
                    self.assertEqual(tokens[0].text, path)
                    self.assertTrue(tokens[0].dynamic)
                    self.assertIs(self.plugin._unwrap_command(tokens)[0], tokens[0])
                    self.assertIsNone(self.guard("terminal", command=f'"{path}" "${{HERMES_SKILL_DIR}}/scripts/thing.py"'))

    def test_runtime_placeholder_write_targets_still_fail_closed(self) -> None:
        with patch.object(Path, "resolve", side_effect=AssertionError("dynamic targets must not be resolved")):
            for target in ('"$(ghq root)/github.com/example/project/target"',
                           '"${HOME}/target"', '"${HERMES_SKILL_DIR}/target"'):
                for command in (f"cp /tmp/x {target}", f"echo x > {target}"):
                    with self.subTest(command=command):
                        result = self.guard("terminal", command=command)
                        self.assertEqual(result["action"], "block")
                        self.assertIn("unresolved", result["message"])

    def test_runtime_command_prefix_does_not_exempt_mutators_or_inline_evaluation(self) -> None:
        for prefix in ("${HOME}", "$HOME", "${HERMES_SKILL_DIR}", "$(ghq root)"):
            for invocation in (f"rm {self.managed}", f"cp /tmp/x {self.managed}",
                               f"python -c 'open(\"{self.managed}\", \"w\")'",
                               f"bash -c 'rm {self.managed}'"):
                command = f"{prefix}/bin/{invocation}"
                with self.subTest(command=command):
                    self.assertEqual(self.guard("terminal", command=command)["action"], "block")

    def test_other_dynamic_command_forms_and_substitutions_remain_opaque(self) -> None:
        commands = (
            f"$CMD {self.managed}",
            f"${{HOME}}/bin/$CMD {self.managed}",
            f"${{HERMES_SKILL_DIR}}/scripts/*.sh {self.managed}",
            f'"$(ghq root; cp /tmp/x {self.managed})/bin/python" script.py',
            f'"$(ghq root > {self.managed})/bin/python" script.py',
            f'"$(ghq root)$(cp /tmp/x {self.managed})/bin/python" script.py',
            f'"$(ghq root $(cp /tmp/x {self.managed}))/bin/python" script.py',
            '"$(ghq root )/bin/python" "${HERMES_SKILL_DIR}/scripts/thing.py"',
        )
        for command in commands:
            with self.subTest(command=command):
                result = self.guard("terminal", command=command)
                self.assertEqual(result["action"], "block")
                self.assertIn("Conservatively blocked", result["message"])

    def test_cwd_changes_only_affect_mutations(self) -> None:
        for directory in ("/tmp", str(self.skills), '"${HERMES_SKILL_DIR}"'):
            for suffix in ("pwd", "ls", f"python {self.script}",
                           'python "${HERMES_SKILL_DIR}/scripts/thing.py"',
                           "echo x > /tmp/out", "rm /tmp/unrelated-output"):
                command = f"cd {directory} && {suffix}"
                with self.subTest(command=command):
                    self.assertIsNone(self.guard("terminal", command=command))
            for suffix in ("rm relative-file", "echo x > relative-file", f"rm {self.managed}"):
                command = f"cd {directory} && {suffix}"
                with self.subTest(command=command):
                    self.assertEqual(self.guard("terminal", command=command)["action"], "block")

    def test_opaque_evaluation_with_managed_references_is_still_blocked(self) -> None:
        spaced_alias = self.fixture_root / "home alias"
        spaced_alias.symlink_to(self.plugin.MANAGED_ROOT, target_is_directory=True)
        relative = Path(self.managed).relative_to(self.plugin.MANAGED_ROOT)
        with patch.dict("os.environ", {"HOME": str(self.alias)}):
            for reference in (str(spaced_alias / relative), f"~/{relative}", f"${{HOME}}/{relative}",
                              f"$HOME/{relative}", "${HERMES_SKILL_DIR}/SKILL.md"):
                commands = (f"bash -c 'rm \"{reference}\"'",
                            f"python -c 'open(\"{reference}\", \"w\")'",
                            f"echo $(rm \"{reference}\")")
                for command in commands:
                    with self.subTest(command=command):
                        result = self.guard("terminal", command=command)
                        self.assertEqual(result["action"], "block")
                        self.assertIn("Conservatively blocked", result["message"])
        for command in (f"python -c 'print(1)' > {self.managed}",
                        f"node -e 'console.log(1)'; rm {self.managed}",
                        f"git log $(git merge-base main HEAD) > {self.managed}",
                        'python -c"open(\'${HERMES_SKILL_DIR}/SKILL.md\', \'w\')"',
                        'node --eval="require(\'fs\').unlinkSync(\'${HERMES_SKILL_DIR}/SKILL.md\')"',
                        'bash --command="rm ${HERMES_SKILL_DIR}/SKILL.md"'):
            with self.subTest(command=command):
                self.assertEqual(self.guard("terminal", command=command)["action"], "block")

    def test_known_mutator_unresolved_targets_remain_conservative(self) -> None:
        for command in ('rm "$TARGET"', 'cp /tmp/in "$TARGET"', 'tee "$TARGET"',
                        'echo x > "$TARGET"', 'sed -i "s/a/b/" "$TARGET"'):
            with self.subTest(command=command):
                self.assertEqual(self.guard("terminal", command=command)["action"], "block")

    def test_destructive_ancestor_operations(self) -> None:
        for target in (self.skills, self.skills.parent, self.skills.parent.parent,
                       self.plugin.MANAGED_ROOT, self.fixture_root, self.alias):
            for executable in ("rm -rf", "mv", "chmod -R 777"):
                command = f"{executable} {target}" + (" /tmp/out" if executable == "mv" else "")
                with self.subTest(command=command):
                    self.assertEqual(self.guard("terminal", command=command)["action"], "block")
        self.assertIsNone(self.guard("terminal", command=f"rm -rf {self.plugin.MANAGED_ROOT}/plugins"))
        self.assertIsNone(self.guard("terminal", command=f"echo x > {self.fixture_root}/out"))

    def test_unresolved_writes_and_opaque_evaluation_fail_closed(self) -> None:
        commands = (
            f"cp /tmp/in {self.skills}/$TARGET",
            f"rm {self.skills}/*/SKILL.md",
            f'echo x > "{self.skills}/$TARGET"',
            f"TARGET={self.managed}; rm \"$TARGET\"",
            f"bash -c 'rm {self.managed}'",
            f"bash -lc 'rm {self.managed}'",
            f"env VAR=value sudo bash -c 'rm {self.managed}'",
            f"eval 'rm {self.managed}'",
            f". {self.managed}",
            f"python -c \"open('{self.managed}', 'w')\"",
            f"python -O -c \"open('{self.managed}', 'w')\"",
            f"python -Ic \"open('{self.managed}', 'w')\"",
            f"node --eval=\"require('fs').unlinkSync('{self.managed}')\" dummy",
            f"zsh --command 'rm {self.managed}'",
            f"fish -C 'rm {self.managed}' {self.script}",
            f"cp --target-dir={self.skills} /tmp/in",
            f"cp --target-dir {self.skills} /tmp/in",
            f"cp -at{self.skills} /tmp/in",
            f"chmod --ref=/tmp/ref {self.managed}",
            f"echo $(rm {self.managed})",
            f"echo `rm {self.managed}`",
            f"cat <(rm {self.managed})",
            f"env -S 'rm {self.managed}'",
            f"sudo -s 'rm {self.managed}'",
            f"sudo -D {self.skills} rm image-creator-pipeline/SKILL.md",
            f"cd {self.skills} && rm image-creator-pipeline/SKILL.md",
            f"(rm {self.managed})",
            f"echo x > '{self.managed}",
            f"cat <<EOF > {self.managed}\nx\nEOF",
        )
        for command in commands:
            with self.subTest(command=command):
                result = self.guard("terminal", command=command)
                self.assertEqual(result["action"], "block")
                self.assertIn("Conservatively blocked", result["message"])

    def test_comments_escapes_and_literal_wildcards(self) -> None:
        self.assertIsNone(self.guard("terminal", command=f"echo x # rm {self.managed}"))
        for command in (f"echo x # harmless\nrm {self.managed}",
                        f"r\\\nm {self.managed}", f"\\\n rm {self.managed}",
                        f"rm\t{self.managed}", f"rm\v{self.managed}"):
            with self.subTest(command=command):
                self.assertEqual(self.guard("terminal", command=command)["action"], "block")
        self.assertIsNone(self.guard("terminal", command="rm '/tmp/literal-$x-*'"))
        self.assertIsNone(self.guard("terminal", command=f"echo '>' {self.managed}"))

    def test_other_direct_write_methods_are_preserved(self) -> None:
        for prefix in ("*** Add File: ", "*** Update File: ", "*** Delete File: "):
            self.assertEqual(self.guard("patch", patch=f"{prefix}{self.managed}\n")["action"], "block")
        for key in ("name", "path", "file_path"):
            self.assertEqual(self.guard("skill_manage", action="patch", **{key: self.managed})["action"], "block")
        self.assertIsNone(self.guard("skill_manage", action="patch", path=self.learned))

    def test_skill_manage_create_is_left_to_create_dir(self) -> None:
        self.assertIsNone(self.guard("skill_manage", action="create", name="example"))


if __name__ == "__main__":
    unittest.main()
