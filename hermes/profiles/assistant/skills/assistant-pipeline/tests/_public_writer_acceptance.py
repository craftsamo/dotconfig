"""Resolve Writer's writer-pipeline acceptance docs for the Assistant tests.

The canonical rubric lives in this checkout at
`hermes/profiles/writer/skills/writer-pipeline/references/acceptance/`. Tests
read the SAME source Writer's requesters load, so the two never drift.
"""

from _pair import PUBLIC_ROOT


_REL = "hermes/profiles/writer/skills/writer-pipeline/references/acceptance"


def public_acceptance_dir():
    root = PUBLIC_ROOT / _REL
    if not root.is_dir():
        raise FileNotFoundError(
            "Writer-pipeline acceptance docs not found at {}".format(root))
    return root


def public_text(name):
    """Whitespace-collapsed text of an acceptance doc, matching this
    directory's own `text()` helper convention."""
    return " ".join((public_acceptance_dir() / name).read_text().split())


def public_raw(name):
    """Raw text, for callers that split on headings themselves."""
    return (public_acceptance_dir() / name).read_text()
