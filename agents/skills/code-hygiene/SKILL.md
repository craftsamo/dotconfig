---
name: code-hygiene
description: >-
  Use when tidying working code without changing its behavior, or when writing
  new code that should not need tidying, in JavaScript/JSX, TypeScript/TSX,
  Python, CSS/SCSS/Tailwind or shell (zsh, bash): ad-hoc type definitions that
  duplicate existing ones, scattered magic numbers and strings, declaration
  comments written as `//` or `#` instead of TSDoc/JSDoc/docstrings, dead or
  commented-out code, files carrying several responsibilities (コードを整理,
  汚いコードを片付ける, 型を整理, 定数をまとめる, TSDoc にする, ファイル分割,
  "clean up this code", "tidy the diff", "consolidate types", "extract
  constants", "convert comments to TSDoc/docstrings", "split this file").
  Not for bug fixes, behavior or API changes, performance work, formatter-only
  runs, linter configuration, or moving a system wholesale.
author: CraftSamo
license: MIT
---

<Goal>

Leave code in the shape a careful maintainer of this repository would have
written it: one definition per type and value, named constants in a known
home, declarations documented in the language's own doc-comment form, and
files that each hold one responsibility. Behavior stays identical. The same
standard applies when writing new code, so less needs tidying later.

</Goal>

<Precedence>

Apply rules in this order; a higher source silences a lower one:

1. The repository's instructions (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`,
   nested equivalents).
2. Its tool configuration: linter, formatter, `tsconfig`, `pyproject.toml`,
   Tailwind theme, `.shellcheckrc`, `.editorconfig`.
3. Patterns already established in the surrounding code: where types and
   constants live, file naming, `type` vs `interface`, docstring style.
4. This skill.

When the repository is inconsistent, follow the pattern of the nearest
directory and report the inconsistency instead of choosing a winner for the
whole codebase.

</Precedence>

<Principles>

1. **Reuse before defining.** Before declaring a type, data shape, constant or
   helper, search the codebase for an existing one. Derive from what exists
   instead of restating it; merge duplicates that already drifted apart only
   when they are provably the same thing. A type from another feature that
   happens to have the same fields is not the same thing.
2. **One home per value.** Name a literal when its meaning is not obvious from
   the line or when the same meaning repeats; two equal literals that mean
   different things are two values. Leave self-evident literals (`0`, `1`,
   `""`, an initial accumulator) inline. Keep a named value in the narrowest
   home that covers its users: the top of the file for one file, a sibling
   constants module for a feature, the repository's shared module for several
   features. Do not hoist a value further than its users need.
3. **Doc comments for declarations.** A comment that describes a function,
   class, type, exported constant or module moves into the language's doc
   comment form (TSDoc/JSDoc, docstring, SassDoc where used, a shell function
   header). Convert what exists; do not write new documentation where the code
   had none. A comment that only restates the declaration's name or signature
   is noise (principle 4): delete it instead of converting it. Comments inside
   a body that explain why stay as plain comments. Some doc-comment forms are
   read at runtime; check <BehaviorInvariants> before converting.
4. **Remove noise, not knowledge.** Delete commented-out code, comments that
   narrate an edit ("changed to X", "new:", "fixed"), and comments that restate
   the next line. Keep every comment that carries a reason, a constraint or a
   reference.
5. **Names say intent.** Rename locals and private helpers whose names hide
   their purpose, using the repository's casing and vocabulary. Exported names
   are public surface (see <StructureTiers>).
6. **Simplify only what is provably dead or redundant.** Unused private
   functions, unreachable branches, wrappers that only forward. Anything
   exported or reachable through reflection, routing or configuration is not
   provably unused.
7. **One responsibility per file.** Split a file that mixes concerns, within
   the limits of <StructureTiers>.

</Principles>

<StructureTiers>

File and directory changes carry more risk than edits inside a file. Sort each
one into a tier before acting:

| Tier | Change | Action |
| --- | --- | --- |
| A | Edits inside a file; extracting into a new sibling file in the same directory (types, constants, a hook, a helper, a split of an oversized file), named after the repository's existing pattern | Do it |
| B | Moving or renaming a file, crossing directories, creating a new directory layout, adding or removing a barrel/`index` re-export, changing an exported name or signature | Propose it with the reason and the affected importers; do not do it |
| C | Files whose path is behavior: framework routing directories, files referenced by path from configuration, scripts or other repositories, package entry points and `exports`, Python package `__init__.py` surfaces, shell entry scripts | Report it if it needs attention; never touch it |

Tier C wins over tier A: a new sibling file inside a routing directory or any
other tier C location can itself become behavior (a route, an entry point),
so it is not created there. A tier A extraction must not create an import
cycle and must update every importer in the same change.

</StructureTiers>

<BehaviorInvariants>

The tidied code must keep all of these unchanged:

- public API: exported names, signatures, types visible to consumers, module
  and package entry points;
- runtime output: return values, rendered markup, serialized data, CLI output,
  exit codes, log lines other code or people rely on;
- evaluation order and side effects, including import-time side effects;
- error paths: which errors are raised, when, and with what messages;
- identity and timing semantics: object identity passed into memoization or
  dependency arrays, cascade order in CSS, word splitting in shell.

Edits that look like comments or typing can be read at runtime (a docstring
as `__doc__`, an annotation, a CSS custom property, an exported type); check
each against this list before making it. The language references name the
cases.

When a cleanup would change any of these, it is not hygiene: leave the code,
and report the change as a proposal. An edit whose effect you would describe
as different observable output (help text that now appears, a value that now
resolves differently, a check that now passes) changed behavior, however much
of an improvement it looks.

</BehaviorInvariants>

<Procedure>

1. Fix the scope: the files or diff the request names. Do not widen it.
2. Read the repository's instructions and tool configuration (<Precedence>).
3. Read the language reference for every language in scope:
   - JavaScript, JSX, TypeScript, TSX → `references/js-ts.md`
   - Python → `references/python.md`
   - CSS, SCSS, Tailwind → `references/css.md`
   - zsh, bash, sh → `references/shell.md`
4. Locate the existing homes before editing: shared type modules, constants
   modules, design tokens, shell libraries, and the naming pattern of sibling
   files.
5. Apply the <Principles> one concern at a time; sort every file change into a
   tier first.
6. Run the cheapest checks that cover the scope: typecheck, linter, tests, a
   build, `shellcheck`. A cleanup that turns a check red is reverted, not
   patched forward.
7. Report:
   - each file changed and the principle applied;
   - tier B proposals with reasons and affected importers;
   - tier C observations;
   - behavior-adjacent cleanups deliberately left alone, and why;
   - the checks run and their results.

</Procedure>

<WritingNewCode>

When writing rather than tidying, apply the same principles at the moment of
writing: search for the existing type or constant first, give new values a
home, document a declaration in doc-comment form only where the surrounding
code documents its declarations, and keep new files to one responsibility.
This does not license tidying code outside the task.

</WritingNewCode>

<Gates>

- [ ] Every change stays inside the requested scope.
- [ ] Repository rules and tool configuration were read and win over this
      skill.
- [ ] No new documentation was invented; only existing declaration comments
      were converted.
- [ ] Every file change was tiered; only tier A was performed.
- [ ] <BehaviorInvariants> hold, and the checks that cover the scope pass.

</Gates>
