"""What the user reads in a chat: questions before their cards, and long text as a file."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return " ".join((ROOT / path).read_text(encoding="utf-8").split())


class UserInteractionTests(unittest.TestCase):
    def test_material_reaches_the_user_before_the_card(self):
        text = read("SKILL.md")
        self.assertIn("Files never ride in the reply text of a turn that asks: they would arrive after the card", text)

    def test_long_text_goes_as_a_markdown_file_with_a_short_gist(self):
        text = read("SKILL.md")
        self.assertIn("**Long text goes as a file.** In a Telegram or Discord chat", text)
        self.assertIn("written to a Markdown file in the job's directory and sent with `MEDIA:`", text)
        self.assertIn("the file goes in that question's `context`, so the user has read it before the card", text)


if __name__ == "__main__":
    unittest.main()
