---
name: source-kit
description: >-
  One free Kenney CC0 game asset PACK (icon packs, UI packs, tile sets, …
  from kenney.nl/assets — not a single drawn or generated image, and not a
  per-icon Iconify glyph, see `source-icon` for that), delivered as the
  requested files extracted under an output directory with a provenance
  record and the license evidence. Nothing is drawn or generated. Zero
  spend.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [kit, kenney, cc0, pack, source, free]
    category: hands
    hands: image-creator
    cost: free
    output: "<deliver>/assets/<archive-relative path> for every selected file (incl. the archive's own README/LICENSE/LICENCE/COPYRIGHT, always preserved but only a real LICENSE/LICENCE/COPYRIGHT is ever quoted as license text) + <deliver>/provenance.json + <deliver>/LICENSE.source.txt"
    form:
      pack:
        required: false
        label: "exact Kenney asset slug from kenney.nl/assets/<slug> (e.g. game-icons); required unless `query` is given"
        example: "game-icons"
      query:
        required: false
        label: "search word when the slug is unknown; required unless `pack` is given — exactly one of pack/query per run"
        example: "game icons"
      pick:
        required: false
        label: "shell-style filename pattern(s) against a file's path inside the pack, one per line — fnmatch, not a POSIX glob: `*` matches `/` too — prefer an explicit subset (e.g. `PNG/Black/1x/arrow*.png`); default: every *.png and *.svg in the pack"
        example: "PNG/Black/1x/arrow*.png"
      note:
        required: false
        type: text
---

<Procedure>

1. If the exact slug is not known, run:

   ```
   python3 ${HERMES_SKILL_DIR}/scripts/kenney-fetch.py --search "<query>"
   ```

   It prints `CANDIDATES:` (slug, title, page URL) from the first results
   page only — this never crawls the whole catalog. Return the candidates
   as `Q1:` with your recommendation; the pack choice is Creator's, not
   yours. Stop there.

2. Otherwise run:

   ```
   python3 ${HERMES_SKILL_DIR}/scripts/kenney-fetch.py --pack <slug> --out <deliver> \
     [--pick 'PATTERN' [--pick 'PATTERN' ...]]
   ```

   `--pick` is a shell-style filename pattern (fnmatch), NOT a POSIX
   glob — `*` also matches `/`, so `PNG/*` can reach into every
   subdirectory of PNG/. Prefer an explicit subset over a broad pattern,
   e.g. `--pick 'PNG/Black/1x/arrow*.png'` rather than `--pick 'PNG/*'`.
   Quote every `--pick` (unquoted, the shell expands it against the local
   filesystem before the script ever sees it). It fetches
   `https://kenney.nl/assets/<slug>`, refuses to proceed unless that page
   explicitly links `creativecommons.org/publicdomain/zero/1.0`,
   downloads the pack's zip from `kenney.nl/media/pages/assets/<slug>/…`,
   validates every archive member before writing anything (no traversal,
   no symlinks, no case-collisions, bounded size and count, a corrupt zip
   fails cleanly with no partial output), and extracts every selected
   file into `<deliver>/assets/`, preserving its archive-relative path
   (a zip member at `PNG/Black/1x/arrowDown.png` retains that entire path
   below the delivery's assets directory). Any
   `README`/`LICENSE`/`LICENCE`/`COPYRIGHT` file in the archive, at ANY
   folder depth, is always extracted under `<deliver>/assets/` too,
   regardless of `--pick` — a pack's terms can be embedded inside a
   subdirectory, not only at the root (a pattern broad enough to also
   match one of these on its own, e.g. `--pick '*'`, is deduplicated —
   it is written once, not twice). Only an actual
   `LICENSE`/`LICENCE`/`COPYRIGHT` file is ever quoted as license text
   (chosen deterministically when more than one exists — shallowest path,
   then lexicographic — never the zip's arbitrary internal order); a
   `README` is preserved on disk but is never quoted as license text —
   the pack page's already-verified CC0 link is the license evidence when
   the archive carries no LICENSE-named file. `<deliver>/provenance.json`
   and `<deliver>/LICENSE.source.txt` are written at `<deliver>`'s root,
   next to `assets/`, never inside it. It prints one `RESULT:` line
   (pack, title, output + assets path, file count, zip sha256 + bytes)
   and one `LICENSE:` line. An unknown slug, an unverifiable license, a
   corrupt zip, or an unsafe archive exits non-zero with the reason on
   stderr — never substitute a different pack or ship anyway.

3. Inspect the delivered file list (`RESULT:` and `provenance.json`):
   the count and paths match what was asked (a requested subset, not the
   whole pack, unless the whole pack was explicitly wanted). For a PNG
   subset, run:

   ```
   python3 ${HERMES_SKILL_DIR}/../../scripts/kit-images.py measure <deliver>/assets --out <deliver>/qa
   ```

   `<deliver>/assets` is always where the extracted files live (see
   Output above), so this path is exact, never a guess. The shared
   `kit-images.py measure` helper reports numbers + review sheets, not a
   pass/fail verdict — still a vision call. It measures every PNG under
   the given directory in one call — if the delivered subset holds more
   than 64 PNGs, point it at one category subdirectory under
   `<deliver>/assets/` at a time, with a distinct QA output directory,
   rather than the whole tree. SVG files are not supported by this
   helper; note any SVG-only pick as unmeasured (a GAP, not a failure)
   since this leaf ships files as-is rather than rendering them.
4. `intent: revise` — rerun with a different `--pick`; the same slug +
   pick reproduce the same selected files (the zip itself is not
   guaranteed to keep the same URL or hash across a Kenney re-upload, so
   re-verify `zip_sha256` in `RESULT:` rather than assuming it).

</Procedure>

<QA>

Every check with its evidence, never "looks fine":

- **Pack identity** — `pack=` in `RESULT:` equals the asked slug (or the
  slug chosen from `Q1:` candidates).
- **License** — the `LICENSE:` line names CC0 1.0 Universal (CC0-1.0) and
  the page URL it was verified on; `provenance.json`'s `license` block
  carries the same plus the zip's `sha256`. A run that could not verify
  CC0 on the page never reaches this leaf's success path — it exits
  non-zero instead.
- **Selection** — `provenance.json.selected_files` is a list of
  `{archive_path, output_path}` pairs, ONE ENTRY PER FILE — `archive_path`
  is the file's path inside the zip, `output_path` is that same path
  under `assets/` (`<deliver>/<output_path>` on disk); `selected_count`
  equals that list's length (a pick broad enough to also catch a
  README/LICENSE is deduplicated, never double-counted). It matches the
  asked `--pick` (or the PNG/SVG default when none was given); a `--pick`
  with zero matches is a hard failure, never a silent empty delivery.
- **Safety** — nothing was delivered outside `<deliver>/assets/`;
  `RESULT:` and `provenance.json` are the only evidence needed, the
  archive's internal path safety was already enforced by the script
  before any file touched disk. A corrupt zip fails as one clean line on
  stderr, never a partial `<deliver>/`.
- **License preservation, accurately attributed** —
  `provenance.json`'s `license.archive_license_file` (and
  `archive_license_file_output_path`) name an actual
  LICENSE/LICENCE/COPYRIGHT file ONLY, when the archive carried one; a
  README is never named there even if it is the only document present —
  it is instead listed under `license.reference_documents`
  (`{archive_path, output_path}` per file), and
  `archive_license_file` stays `null`. Either way the file(s) are
  extracted to `<deliver>/assets/`; only the label differs, and
  `LICENSE.source.txt` says explicitly which case it is.
- **Aesthetics are not claimed** — this leaf verifies CC0 licensing and
  archive safety, not that the pack's art style matches the ask; say so
  in the report rather than implying every file was visually reviewed.

A failed check is one rerun (a transient network error) or a `Q<n>:` /
reported gap; it is never silently delivered.

</QA>

<Report>

`source-kit` + the pack slug and title; the extracted files' absolute
paths (or the output directory + count for a large selection); each QA
check with its evidence (the `RESULT:` line, `provenance.json` path);
the `LICENSE:` line verbatim; `spend: free`; any GAP (e.g. an SVG left
unmeasured) and anything Creator must decide (a search's candidates).

</Report>
