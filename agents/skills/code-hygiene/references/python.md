# Python

Read with `SKILL.md`; the repository's `pyproject.toml` (Ruff, mypy, Pyright
settings) and its minimum Python version win over everything here.

## Types

- Search before declaring: an existing `TypedDict`, dataclass, Pydantic
  model, `NamedTuple`, `Protocol` or type alias is reused.
- Write hints in the syntax the minimum supported version allows:
  `list[str]` and `X | None` from 3.9/3.10, `typing.List`/`Optional` only
  where the repository still targets older versions or already uses them.
- A dict shape passed between functions gets a `TypedDict` or a type alias,
  which is annotation-only. Converting the dict itself to a dataclass or
  model changes equality, hashing, `repr` and serialization: that is tier B.
- Closed sets of strings get `Literal[...]` in annotations; introducing an
  `Enum` changes runtime values and is tier B.
- Adding or correcting annotations is safe; changing a runtime default to
  satisfy a type checker is not hygiene.

## Constants

- Module-level `UPPER_SNAKE_CASE`, annotated `Final` when the repository uses
  it.
- A value shared across modules moves to the package's existing constants or
  settings module; do not create a new top-level module for one value.
- Values read from the environment or configuration stay where configuration
  is read.

## Docstrings

- A `#` comment directly above a `def` or `class`, or at the top of a module
  describing it, becomes a docstring in the repository's style (Google,
  NumPy or reST; follow the nearest existing docstring).
- Keep the content; add `Args:`/`Returns:`/`Raises:` sections only for what
  the comment already said.
- Comments inside bodies stay `#`.

## Files and packages

- Tier A: extracting helpers or types into a sibling module in the same
  package, imported by the original module.
- Tier B: moving modules between packages, renaming modules, adding
  re-exports.
- Tier C: `__init__.py` imports and `__all__` (they are the package's public
  surface), console-script and entry-point targets in `pyproject.toml`,
  modules imported by dotted path from configuration (Django settings,
  Celery, plugin registries), `conftest.py` placement.
- An extraction must not create a circular import; when it would, keep the
  code where it is and report it.

## Behavior traps

- Module import order runs top-level code; moving code between modules can
  change when it runs.
- A mutable default argument is a bug, not a style issue: report it instead of
  fixing it inside a cleanup.
- `is` vs `==`, truthiness checks vs `is None`, and `dict` ordering
  assumptions change results.
- Renaming a function changes pickled references, logging names and
  `__name__`-based registries.
