---
name: motion-vocabulary-upkeep
description: >-
  Use when adding to, deepening or auditing the shared motion-vocabulary
  skill — its names, video builds or web builds — especially when motion
  names or expressions come from a source such as an article, a motion
  catalogue site or an X post (「この記事の表現を取り込んで」,
  「モーション名を辞書に追加」, 「動きの語彙を深めて」, "add these animation names to
  the vocabulary", "audit the motion vocabulary"). Not hands option
  references such as styles or themes (hermes-hands-references), not producing
  a video, and not implementing animation in a project (motion-vocabulary).
license: MIT
compatibility: OpenCode maintaining this dotconfig repository in a task worktree; the Hermes test interpreter; Node for one-off source extraction.
---

<Goal>

Grow and keep the motion vocabulary usable: every motion has one name (with
Japanese aliases) that a storyboard author, Creator and a web developer
share, a description that says what makes it read as itself, and a build for
each medium. Names may come from anywhere; wording, code and numbers from a
source never enter the repository. The caller (the Hermes Assistant or a
person) owns scope and acceptance; this Skill owns the procedure.

</Goal>

<Model>

Read these before editing; they are the contract the audit enforces.

- The skill lives in agents/curated/motion-vocabulary. Its SKILL.md routes
  each authoring decision to a names file (references, one per area), its
  video builds (references/video) and, for web areas, its web builds
  (references/web). Names files hold `| Name | Feel | For | Looks like | The
  tell |` (timing omits For; drawn looks, compositions and film structures
  drop the motion columns); video files `| Name | Built with |`; web files
  `| Name | Trigger | Web build | Reduced motion |`. A new decision area is a
  names file, a video file and a router row, plus a web file when the area
  ships on pages.
- Name is `english name（日本語、別名）`. Feel is one or two of the five words
  defined in the timing names file's "## Feel". The tell is the detail that
  makes the entry read as itself, ending with "vs `neighbour`: difference"
  when a close neighbour exists. A medium row names an entry of the same
  area's names file.
- Names files and video builds are rule-free (the decision record
  storyboard-vocabulary-rule-free.md): no numeric defaults, cautions,
  avoid-lists or scores. Names stay medium-neutral; timeline framing, seekable
  builds, seeded randomness and supplied-art handling belong to the video
  files. Web builds carry typical values, `prefers-reduced-motion` forms and
  fallbacks for non-baseline features.
- Hermes video-creator pins the skill in skills.external_dirs and its five
  authored leaves read SKILL.md and the core names file to plan, then the
  video rows to build; Creator reads names only. Size limits: core names under
  60 KB, other names under 45 KB, video files under 25 KB, web files under
  48 KB.
- The audit script audit-motion-vocabulary.py (hermes scripts) checks shape,
  routing, sizes, references, descriptive tells, medium-row parity, seekable
  video builds and, with `--source`, eight-word overlap with source prose.

</Model>

<Procedure>

1. Work in a task worktree, never the live `~/.config` checkout (`~/.hermes`
   and the shared skills root link into it). Read `hermes/AGENTS.md`.
2. Capture the source outside the repository, in the session's scratch
   directory: the names (and their Japanese forms), any feel or usage tags,
   and the source's descriptive prose saved as plain text for `--source`.
   Read a post's attached images with an X search that understands images;
   for a site, prefer its published data files over scraping rendered
   pages. Record the source and the date only for the commit message.
3. Inventory before writing. Normalise names and match them against existing
   Name cells (English part and aliases). A match becomes an alias on the
   existing entry. A new name goes to the area whose router row describes the
   decision it serves. Report the counts (aliases, new rows per area, new
   areas) to the caller before bulk writing.
4. Write the names rows in our own words, then the video row and, for a web
   area, the web row of each new entry. Give writers the existing rows and, at
   most, the source's descriptions as understanding material with an explicit
   ban on reusing sentences, code or numbers. One writer per file; split a
   large file into scratch parts by section and merge them yourself, because
   parallel edits to one file lose work. Ask writers to save after every
   section so an interrupted run resumes. Expect the last sections of a long
   assignment to come back thin: measure row length and send thin rows back
   in small batches.
5. Audit until clean:

   ```sh
   hermes-python --test hermes/scripts/audit-motion-vocabulary.py --source <scratch>/source.txt
   ```

   Rewrite any flagged row in fresh wording rather than nudging a word or
   two; a row that echoes the source usually echoes it in more than one
   place. Then run, from `hermes/`, the vocabulary tests with the Hermes
   interpreter and `--import-mode=importlib`
   (`test_audit_motion_vocabulary.py`, `test_video_creator_routing.py`,
   `test_create_promotion.py`, `test_create_story.py`,
   `test_creator_entry_contract.py`) and the skill's structure test from the
   repository root:

   ```sh
   uv run --with pytest python -m pytest agents/tests/test_motion_vocabulary.py
   ```

6. Forward-test in fresh read-only sessions: a storyboard (names first, then
   video rows), a Creator revision from feel words (names only) and a web
   request (an LP with bouncy scroll reveals). Check that the router opens
   the right files first and that each chosen entry yields a concrete detail
   to hand an animator or a developer. Include one near miss.
7. Review the change for descriptive-only names, seekable video builds,
   supplied art, accuracy of Japanese typesetting terms and, for web rows,
   correct web APIs, fallbacks and reduced-motion forms.
8. Commit one concern at a time with the git-commit workflow: aliases, new
   rows, a new area with its router row, web rows, audit or test changes.
   Credit the source in the commit body (names adopted, descriptions our
   own). The vocabulary's own files never cite sources. New files reach
   Hermes and other CLIs only after merge, when a person runs the
   repository's install.sh before the next session.

</Procedure>

<Completion>

Done means: the audit reports 0 errors with the source supplied; the
vocabulary tests pass; the forward tests routed correctly; the commits are
split by concern and credit the source; and the report to the caller lists
what was adopted, what was skipped and why, and what still needs a person
(merge, install.sh, gateway restart).

</Completion>
