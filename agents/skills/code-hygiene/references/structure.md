# File structure: splits, merges and moves

Read with `SKILL.md` whenever a change splits, merges or moves files, or
proposes to. Tier A splits follow principle 7; this file adds where code
belongs and what a tier B proposal must hold.

## Where code belongs

These rules decide what to propose and where new code goes; a move they call
for is still tier B, proposed and not made.

- Follow the layout the repository already uses (by feature, by layer). A
  tidying pass does not change the convention; report a convention problem
  instead of proposing to re-layer the codebase.
- Code lives with its users. Code that one feature uses belongs in that
  feature, even when it sits in a shared folder today; code that several
  features use belongs in their nearest shared home, no higher.
- Dependencies point one way: features import shared code, and shared code
  never imports a feature. Where the repository gives features a public
  entry (an `index.ts`, an `__init__.py`), another feature imports only
  through it. A move must not create a cycle.
- A file should not import its own directory's barrel (`index.ts`,
  `__init__.py`); it imports the sibling file directly. That edit is tier A
  as long as the barrel stays as it is and nothing depends on the import
  order it gave (side effects in the barrel, a test mocking the barrel path).
- Prefer few deep modules to many shallow ones: no file per function, no
  directory per file, no new folder for one or two files.
- A grab-bag module (`utils`, `helpers`, `common`) is taken apart by users,
  not by topic: propose moving each part to where its users are before
  proposing new shared files.

## Merging

Propose merging existing small files that always change together, showing
the commits that touched them together (`git log --oneline -- <files>`). A
single importer strengthens the case but is not one alone: a file holding a
separate concept, or a per-file sibling the naming pattern calls for, stays.
Merge into the importer or into one file named after the shared concept.

## What a tier B proposal holds

1. The change: current path → target path, or the files to merge or split.
2. The reason in terms of users, owners or co-change, never size or taste.
3. Every importer to update: search for the path and for each exported name,
   including tests, dynamic imports and paths written as strings.
4. The configuration and public paths it affects: the tool globs and names
   from `SKILL.md` `<StructureTiers>`, path aliases, `package.json`
   `exports` and `files`, `__init__.py` re-exports, CODEOWNERS, CI path
   filters. Write "none found"
   after checking, rather than leaving it out.
5. Migration steps: move with `git mv` in a commit with no content edits, so
   history follows the file; update importers next; for a public path, leave
   a re-export at the old path marked deprecated and remove it in a later
   release.
6. The risk: what could break, and whether the checks would show it.
