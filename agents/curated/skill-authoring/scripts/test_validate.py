# SPDX-License-Identifier: MIT
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "PyYAML>=6.0,<7",
# ]
# ///
"""Regression tests for the read-only Skill validator."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate import Finding, validate_skill  # noqa: E402


def _messages(findings: list[Finding], level: str) -> list[str]:
    return [finding.message for finding in findings if finding.level == level]


class ValidateSkillTests(unittest.TestCase):
    def _skill(
        self,
        root: Path,
        name: str = "example-skill",
        *,
        frontmatter_name: str | None = None,
        description: str | None = "Use when testing a complete example Skill.",
        body: str = "# Example Skill\n\nFollow the concrete workflow.\n",
        extra_frontmatter: str = "",
    ) -> Path:
        skill_root = root / name
        skill_root.mkdir()
        fields = [f"name: {frontmatter_name or name}"]
        if description is not None:
            fields.append(f"description: {description}")
        if extra_frontmatter:
            fields.append(extra_frontmatter)
        skill_root.joinpath("SKILL.md").write_text(
            "---\n" + "\n".join(fields) + "\n---\n\n" + body,
            encoding="utf-8",
        )
        return skill_root

    def test_accepts_complete_skill_and_existing_resources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root = self._skill(
                Path(directory),
                body=(
                    "# Example Skill\n\n"
                    "Read [the detailed rules](references/rules.md).\n"
                    "Replace the template [alert URL](ALERT_URL).\n"
                    "Run `scripts/check.py` after editing.\n"
                ),
            )
            (skill_root / "references").mkdir()
            (skill_root / "references" / "rules.md").write_text(
                "# Rules\n", encoding="utf-8"
            )
            (skill_root / "scripts").mkdir()
            (skill_root / "scripts" / "check.py").write_text(
                "print('ok')\n", encoding="utf-8"
            )

            findings = validate_skill(skill_root)

            self.assertEqual([], _messages(findings, "ERROR"))
            self.assertEqual([], _messages(findings, "WARNING"))

    def test_rejects_missing_description(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root = self._skill(Path(directory), description=None)

            errors = _messages(validate_skill(skill_root), "ERROR")

            self.assertIn("missing required field 'description'", errors)

    def test_rejects_invalid_name_and_warns_on_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root = self._skill(
                Path(directory), frontmatter_name="Wrong_Name"
            )

            findings = validate_skill(skill_root)
            errors = _messages(findings, "ERROR")
            warnings = _messages(findings, "WARNING")

            self.assertTrue(any("single hyphens" in message for message in errors))
            self.assertTrue(any("nested layout" in message for message in warnings))

    def test_rejects_placeholder_and_dangling_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root = self._skill(
                Path(directory),
                body=(
                    "# Example Skill\n\n"
                    "[TODO: replace this workflow]\n"
                    "Read [missing rules](references/missing.md).\n"
                    "Read [missing reference][unknown-rules].\n"
                    "Run `scripts/missing.py`.\n"
                ),
            )

            errors = _messages(validate_skill(skill_root), "ERROR")

            self.assertTrue(any("TODO/FIXME" in message for message in errors))
            self.assertTrue(any("Markdown link" in message for message in errors))
            self.assertTrue(any("reference-style" in message for message in errors))
            self.assertTrue(any("referenced resource" in message for message in errors))

    def test_ignores_example_links_and_accepts_balanced_and_reference_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root = self._skill(
                Path(directory),
                body=(
                    "# Example Skill\n\n"
                    "````markdown\n"
                    "```markdown\n"
                    "[fenced example](references/missing.md)\n"
                    "```\n\n"
                    "TODO: this is example content, not a scaffold.\n"
                    "````\n\n"
                    "Show ``Use `code` and [inline example](references/missing.md)`` literally.\n"
                    "> ````markdown\n"
                    "> [quoted example](references/missing.md)\n"
                    "> TODO: quoted example content.\n"
                    "> ````\n\n"
                    "Read [balanced](references/rules(v2).md).\n"
                    "Read [defined rules][rules].\n\n"
                    "[rules]: references/rules.md\n"
                ),
            )
            references = skill_root / "references"
            references.mkdir()
            (references / "rules(v2).md").write_text("# V2\n", encoding="utf-8")
            (references / "rules.md").write_text("# Rules\n", encoding="utf-8")

            findings = validate_skill(skill_root)

            self.assertEqual([], _messages(findings, "ERROR"))

    def test_rejects_links_and_symlinks_that_escape_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside_markdown = root / "outside.md"
            outside_markdown.write_text("# Outside\n", encoding="utf-8")
            outside_script = root / "outside.py"
            outside_script.write_text("print('outside')\n", encoding="utf-8")
            skill_root = self._skill(
                root,
                body=(
                    "# Example Skill\n\n"
                    "Read [outside](../outside.md).\n"
                    "Read [file outside](file:../outside.md).\n"
                    "Read [Windows path](C:/outside.md).\n"
                    "Run `scripts/linked.py`.\n"
                ),
            )
            scripts = skill_root / "scripts"
            scripts.mkdir()
            (scripts / "linked.py").symlink_to(outside_script)

            findings = validate_skill(skill_root)
            errors = _messages(findings, "ERROR")
            warnings = _messages(findings, "WARNING")

            self.assertGreaterEqual(
                sum("escapes the Skill" in message for message in errors), 2
            )
            self.assertTrue(any("symlink resolves outside" in message for message in errors))
            self.assertTrue(any("C:/outside.md" in message for message in warnings))

    def test_rejects_ambiguous_yaml_keys(self) -> None:
        cases = {
            "non-string": "1: value\nname: example-skill\ndescription: Example.",
            "duplicate": (
                "name: example-skill\nname: duplicate\ndescription: Example."
            ),
        }
        for label, frontmatter in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                skill_root = Path(directory) / "example-skill"
                skill_root.mkdir()
                (skill_root / "SKILL.md").write_text(
                    f"---\n{frontmatter}\n---\n\n# Example\n", encoding="utf-8"
                )

                errors = _messages(validate_skill(skill_root), "ERROR")

                self.assertTrue(any("invalid YAML frontmatter" in message for message in errors))

    def test_placeholder_detection_is_specific_and_handles_markdown_prefixes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root = self._skill(
                Path(directory),
                description="Use when replacing document [TODO] markers safely.",
                body=(
                    "# Example Skill\n\n"
                    "- TODO: replace this section\n"
                    "> <!-- FIXME: add the missing gate -->\n"
                ),
            )

            errors = _messages(validate_skill(skill_root), "ERROR")

            self.assertEqual(2, len(errors))
            self.assertTrue(all("TODO/FIXME" in message for message in errors))

    def test_rejects_description_that_starts_with_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root = self._skill(
                Path(directory), description='"TODO: explain the concrete triggers"'
            )

            errors = _messages(validate_skill(skill_root), "ERROR")

            self.assertTrue(any("scaffold placeholder" in message for message in errors))

    def test_rejects_nested_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root = self._skill(Path(directory))
            nested = skill_root / "references" / "nested"
            nested.mkdir(parents=True)
            (nested / "SKILL.md").write_text(
                "---\nname: nested\ndescription: Nested.\n---\n\n# Nested\n",
                encoding="utf-8",
            )

            errors = _messages(validate_skill(skill_root), "ERROR")

            self.assertTrue(any("nested SKILL.md" in message for message in errors))

    def test_warnings_do_not_become_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            long_body = "# Example Skill\n" + "\n".join(
                f"Line {index}." for index in range(510)
            )
            skill_root = self._skill(
                Path(directory), body=long_body, extra_frontmatter="author: Example"
            )
            (skill_root / "README.md").write_text("Extra.\n", encoding="utf-8")
            (skill_root / "assets").mkdir()

            findings = validate_skill(skill_root)

            self.assertEqual([], _messages(findings, "ERROR"))
            warnings = _messages(findings, "WARNING")
            self.assertTrue(any("non-portable" in message for message in warnings))
            self.assertTrue(any("progressive disclosure" in message for message in warnings))
            self.assertTrue(any("auxiliary document" in message for message in warnings))
            self.assertTrue(any("empty resource directory" in message for message in warnings))

    def test_validator_accepts_its_own_skill(self) -> None:
        skill_root = Path(__file__).resolve().parents[1]

        errors = _messages(validate_skill(skill_root), "ERROR")

        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
