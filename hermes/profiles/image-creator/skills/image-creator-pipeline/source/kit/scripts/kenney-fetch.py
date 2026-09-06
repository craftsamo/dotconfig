#!/usr/bin/env python3
"""kenney-fetch.py — the `source-kit` leaf's fetcher: one free Kenney CC0
game asset PACK (not a single icon — see `source-icon` for that), delivered
as the requested files extracted under an output directory plus a
provenance record. Nothing is drawn or generated. Zero spend.

Usage:
  kenney-fetch.py --search WORD
      List candidate packs (slug, title, page URL) from kenney.nl/assets.
      Prints CANDIDATES lines and exits; writes nothing. The Creator picks
      a slug, never this script.

  kenney-fetch.py --pack SLUG --out DIR [--pick GLOB]...
      Fetch https://kenney.nl/assets/SLUG, verify the page names a CC0
      license, download its zip, verify it is safe, and extract the files
      matching --pick (repeatable; a shell-style filename pattern —
      fnmatch, NOT a POSIX glob: `*` matches `/` too, so `PNG/*` can
      reach into subdirectories of PNG/ — against the zip member's path,
      e.g. --pick 'PNG/Black/1x/arrow*.png' for a specific explicit
      subset; quote every pattern so the shell does not expand it first)
      into DIR/assets/, preserving each file's archive-relative path
      (DIR/assets/PNG/Black/1x/arrowDown.png for a zip member at
      PNG/Black/1x/arrowDown.png). Any README/LICENSE/LICENCE/COPYRIGHT
      file in the archive, at ANY folder depth, is always preserved under
      DIR/assets/ regardless of --pick — a pack's terms can be embedded
      inside a subdirectory, not only at the root. Only an actual
      LICENSE/LICENCE/COPYRIGHT file is ever quoted as license text in
      provenance.json / LICENSE.source.txt (chosen deterministically —
      shallowest path, then lexicographic — never the zip's arbitrary
      central directory order); a README is preserved but recorded as a
      reference document, never as license evidence — the pack page's
      already-verified CC0 link stays the sole license evidence when the
      archive carries no LICENSE-named file. Without --pick, only *.png
      and *.svg members are extracted (audio/fonts/docs are skipped by
      default to avoid pulling a whole pack unasked). Writes
      DIR/provenance.json and DIR/LICENSE.source.txt (at DIR's root, next
      to assets/, never inside it) on success. DIR must not already exist
      as a non-empty directory or a symlink.

Network: stdlib urllib only, https to kenney.nl / www.kenney.nl only,
redirects followed up to a small limit and re-checked against that same
host allowlist each hop. Search looks at the first results page only —
this never crawls the whole catalog.

Safety: the zip is downloaded to a size-bounded temp file, sha256'd, then
opened read-only and validated member-by-member (no absolute paths, no
`..` traversal, no backslashes, no NUL bytes, no drive letters, no
symlinks, no case-insensitive duplicate destinations) before anything is
written to disk; extraction happens into a temp staging directory beside
DIR and is renamed into place only after every check passes.

Exit status: 0 on success (or on a completed --search), 1 on any refusal
(bad slug, license not verified, unsafe zip member, no --pick match,
existing/symlinked output, network error, ...) with a one-line reason on
stderr.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import posixpath
import re
import shutil
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import PurePosixPath

PROG = "kenney-fetch"
ALLOWED_HOSTS = {"kenney.nl", "www.kenney.nl"}
USER_AGENT = "kenney-fetch/1.0 (+hermes image-creator source-kit; CC0 asset fetcher)"
CC0_URL_RE = re.compile(r"creativecommons\.org/publicdomain/zero/1\.0/?", re.IGNORECASE)
CREATIVECOMMONS_RE = re.compile(r"creativecommons\.org", re.IGNORECASE)
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

MAX_REDIRECTS = 5
PAGE_TIMEOUT = 20
ZIP_TIMEOUT = 60
MAX_PAGE_BYTES = 5 * 1024 * 1024          # 5 MB of HTML is already generous
MAX_ZIP_DOWNLOAD_BYTES = 300 * 1024 * 1024  # 300 MB compressed cap
MAX_ZIP_ENTRIES = 20000
MAX_SELECTED_MEMBERS = 5000
MAX_SELECTED_UNCOMPRESSED_BYTES = 500 * 1024 * 1024  # 500 MB extracted cap
DEFAULT_PICKS = ("*.png", "*.PNG", "*.svg", "*.SVG")
ASSETS_SUBDIR = "assets"  # every selected file lands under DIR/assets/<archive-relative path>
# Matched against a member's BASENAME (posixpath.basename), so this fires at
# any folder depth — a pack's license terms may be embedded in a
# subdirectory, not only at the archive root. The keyword must be the whole
# name or be followed by a separator (README.txt, LICENSE-CC0.md,
# copyright_notice.pdf), not just be a prefix of an unrelated word
# (licensed-report.pdf is not a license file).
LICENSE_NAME_RE = re.compile(r"^(readme|license|licence|copyright)(?:[._\-].*)?$", re.IGNORECASE)


class FetchError(Exception):
    """A refusal: bad input, unverifiable license, or unsafe archive."""


# ── networking ──────────────────────────────────────────────────────────


def _host_allowed(url: str) -> bool:
    netloc = urllib.parse.urlsplit(url).netloc.split("@")[-1].split(":")[0].lower()
    return netloc in ALLOWED_HOSTS


def _https_get(url: str, *, timeout: int, max_bytes: int) -> bytes:
    """GET url over https, staying on the host allowlist across redirects,
    and refusing to read more than max_bytes of the response body."""
    if urllib.parse.urlsplit(url).scheme != "https" or not _host_allowed(url):
        raise FetchError(f"refusing non-allowlisted URL: {url}")
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        req = urllib.request.Request(current, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                final_url = resp.geturl()
                if urllib.parse.urlsplit(final_url).scheme != "https" or not _host_allowed(final_url):
                    raise FetchError(f"redirected off the allowlist: {final_url}")
                data = resp.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise FetchError(f"response exceeded {max_bytes} bytes: {current}")
                return data
        except urllib.error.HTTPError as exc:
            raise FetchError(f"HTTP {exc.code} fetching {current}") from exc
        except urllib.error.URLError as exc:
            raise FetchError(f"network error fetching {current}: {exc.reason}") from exc
    raise FetchError(f"too many redirects: {url}")


def _download_zip(url: str, dest_path: str) -> tuple[str, int]:
    """Stream-download url to dest_path, bounded by MAX_ZIP_DOWNLOAD_BYTES,
    returning (sha256_hex, byte_count). Redirects are host-checked like _https_get."""
    if urllib.parse.urlsplit(url).scheme != "https" or not _host_allowed(url):
        raise FetchError(f"refusing non-allowlisted zip URL: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    total = 0
    try:
        with urllib.request.urlopen(req, timeout=ZIP_TIMEOUT) as resp:
            final_url = resp.geturl()
            if urllib.parse.urlsplit(final_url).scheme != "https" or not _host_allowed(final_url):
                raise FetchError(f"zip redirected off the allowlist: {final_url}")
            with open(dest_path, "wb") as fh:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_ZIP_DOWNLOAD_BYTES:
                        raise FetchError(
                            f"zip exceeded the {MAX_ZIP_DOWNLOAD_BYTES}-byte download cap: {url}"
                        )
                    digest.update(chunk)
                    fh.write(chunk)
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code} downloading {url}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"network error downloading {url}: {exc.reason}") from exc
    return digest.hexdigest(), total


# ── HTML parsing (stdlib only) ──────────────────────────────────────────


class SearchResultsParser(HTMLParser):
    """Collects (slug, title) pairs from `<h2><a href='.../assets/SLUG'>Title</a></h2>`
    asset cards on a kenney.nl/assets search results page. Pagination links
    and category chips live outside <h2> and are ignored on purpose."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[tuple[str, str]] = []
        self._in_h2 = False
        self._href: str | None = None
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h2":
            self._in_h2 = True
            self._href = None
            self._title_parts = []
        elif tag == "a" and self._in_h2:
            href = dict(attrs).get("href") or ""
            self._href = href

    def handle_data(self, data: str) -> None:
        if self._in_h2:
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2":
            title = "".join(self._title_parts).strip()
            if self._href and title:
                slug = self._slug_from_href(self._href)
                if slug:
                    self.results.append((slug, title))
            self._in_h2 = False
            self._href = None
            self._title_parts = []

    @staticmethod
    def _slug_from_href(href: str) -> str | None:
        parsed = urllib.parse.urlsplit(href)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) != 2 or parts[0] != "assets":
            return None
        slug = parts[1]
        return slug if SLUG_RE.match(slug) else None


class PackPageParser(HTMLParser):
    """Pulls what `source-kit` needs off a kenney.nl/assets/SLUG page: the
    first <h1> as the title, every .zip href, and whether a CC0 (or any
    other creativecommons.org) license link is present."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str | None = None
        self.zip_hrefs: list[str] = []
        self.cc0_seen = False
        self.other_cc_hrefs: list[str] = []
        self._in_title_h1 = False
        self._title_parts: list[str] = []
        self._h1_done = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        adict = dict(attrs)
        if tag == "h1" and not self._h1_done:
            self._in_title_h1 = True
            self._title_parts = []
        if tag == "a":
            href = adict.get("href") or ""
            if href.lower().endswith(".zip"):
                self.zip_hrefs.append(href)
            elif CC0_URL_RE.search(href):
                self.cc0_seen = True
            elif CREATIVECOMMONS_RE.search(href):
                self.other_cc_hrefs.append(href)

    def handle_data(self, data: str) -> None:
        if self._in_title_h1:
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1" and self._in_title_h1:
            self.title = "".join(self._title_parts).strip()
            self._in_title_h1 = False
            self._h1_done = True


# ── search ──────────────────────────────────────────────────────────────


def do_search(word: str) -> int:
    url = "https://kenney.nl/assets?" + urllib.parse.urlencode({"search": word})
    html = _https_get(url, timeout=PAGE_TIMEOUT, max_bytes=MAX_PAGE_BYTES).decode(
        "utf-8", errors="replace"
    )
    parser = SearchResultsParser()
    parser.feed(html)
    if not parser.results:
        print(f"CANDIDATES: none for {word!r} ({url})")
        return 0
    print(f"CANDIDATES: {len(parser.results)} result(s) for {word!r} (first page, {url})")
    for slug, title in parser.results:
        print(f"  {slug}\t{title}\thttps://kenney.nl/assets/{slug}")
    return 0


# ── pack page + license verification ────────────────────────────────────


def fetch_pack_page(slug: str) -> tuple[str, PackPageParser]:
    if not SLUG_RE.match(slug):
        raise FetchError(f"--pack must be a slug like game-icons, got: {slug}")
    page_url = f"https://kenney.nl/assets/{slug}"
    html = _https_get(page_url, timeout=PAGE_TIMEOUT, max_bytes=MAX_PAGE_BYTES).decode(
        "utf-8", errors="replace"
    )
    parser = PackPageParser()
    parser.feed(html)
    return page_url, parser


def resolve_zip_url(page_url: str, parser: PackPageParser) -> str:
    if not parser.zip_hrefs:
        raise FetchError(f"no .zip link found on {page_url} — report as a gap")
    resolved = []
    for href in parser.zip_hrefs:
        candidate = urllib.parse.urljoin(page_url, href)
        parts = urllib.parse.urlsplit(candidate)
        if parts.scheme != "https" or not _host_allowed(candidate):
            continue
        slug = PurePosixPath(urllib.parse.urlsplit(page_url).path).name
        if not parts.path.startswith(f"/media/pages/assets/{slug}/"):
            continue
        resolved.append(candidate)
    if not resolved:
        raise FetchError(
            f"the .zip link(s) on {page_url} did not resolve to an allowlisted "
            f"kenney.nl /media/pages/assets/<slug>/ path"
        )
    unique = sorted(set(resolved))
    if len(unique) > 1:
        raise FetchError(f"ambiguous: {len(unique)} distinct .zip links on {page_url}: {unique}")
    return unique[0]


def verify_cc0(page_url: str, parser: PackPageParser) -> None:
    if parser.cc0_seen:
        return
    if parser.other_cc_hrefs:
        raise FetchError(
            f"license on {page_url} is not verified CC0 (found: {parser.other_cc_hrefs[0]}); refusing"
        )
    raise FetchError(f"no license link found on {page_url}; refusing an unverified license")


# ── zip safety + extraction ──────────────────────────────────────────────


def _is_symlink_entry(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode) if mode else False


def _dedup_preserve_order(items: list[zipfile.ZipInfo]) -> list[zipfile.ZipInfo]:
    """De-duplicate by object identity, keeping first-seen order stable.
    `--pick '*'` (or any pattern broad enough to also match a
    README/LICENSE) puts the same ZipInfo in both `picked` and
    `license_files`; without this, extraction would write it twice and
    both `selected_count` and `selected_files` would double-count it."""
    seen: set[int] = set()
    out: list[zipfile.ZipInfo] = []
    for item in items:
        if id(item) not in seen:
            seen.add(id(item))
            out.append(item)
    return out


def _validate_member_name(name: str) -> str:
    """Return the safe, normalized relative POSIX path for a zip member
    name, or raise FetchError. Rejects absolute paths, `..` traversal,
    backslashes, NUL bytes, and drive letters."""
    if "\x00" in name:
        raise FetchError(f"zip member has a NUL byte in its name: {name!r}")
    if "\\" in name:
        raise FetchError(f"zip member uses a backslash path separator: {name!r}")
    if re.match(r"^[A-Za-z]:", name):
        raise FetchError(f"zip member has a drive letter: {name!r}")
    if name.startswith("/"):
        raise FetchError(f"zip member is an absolute path: {name!r}")
    normalized = posixpath.normpath(name)
    if normalized == ".." or normalized.startswith("../") or normalized.startswith("/"):
        raise FetchError(f"zip member escapes the archive root: {name!r}")
    return normalized


def inspect_zip(zip_path: str) -> zipfile.ZipFile:
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as exc:
        raise FetchError(f"corrupt zip (not a valid zip archive): {exc}") from exc
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_ENTRIES:
        zf.close()
        raise FetchError(f"zip has {len(infos)} entries, over the {MAX_ZIP_ENTRIES} cap")
    for info in infos:
        _validate_member_name(info.filename)
        if _is_symlink_entry(info):
            zf.close()
            raise FetchError(f"zip contains a symlink entry, refusing the whole pack: {info.filename!r}")
    return zf


def select_members(
    zf: zipfile.ZipFile, picks: tuple[str, ...], *, require_each_match: bool = True
) -> tuple[list[zipfile.ZipInfo], list[zipfile.ZipInfo]]:
    """Return (picked, license_files) — the members matching --pick (or the
    defaults) plus any README/LICENSE/LICENCE/COPYRIGHT file at ANY folder
    depth, deduplicated, with every safety check re-applied to the final
    selection.

    An explicit --pick (require_each_match=True, the default) fails if any
    ONE of its patterns matches nothing — a typo must never silently
    deliver less than asked. The built-in PNG/SVG default
    (require_each_match=False, used only when the caller gave no --pick at
    all) is an OR of several case variants; a pack with no
    uppercase-extension files is not an error, only an overall empty
    selection is.

    A pattern is a shell-style filename pattern (fnmatch), matched against
    the member's full path — unlike a POSIX glob, `*` also matches `/`, so
    e.g. `PNG/*` reaches into every subdirectory of PNG/."""
    infos = [i for i in zf.infolist() if not i.is_dir()]

    license_files = [
        i for i in infos if LICENSE_NAME_RE.match(posixpath.basename(i.filename))
    ]

    picked: list[zipfile.ZipInfo] = []
    seen_pick_ids = set()
    for pattern in picks:
        matches = [i for i in infos if fnmatch.fnmatchcase(i.filename, pattern)]
        if not matches and require_each_match:
            raise FetchError(f"--pick {pattern!r} matched nothing in the zip")
        for m in matches:
            if id(m) not in seen_pick_ids:
                seen_pick_ids.add(id(m))
                picked.append(m)
    if not picked and not require_each_match:
        raise FetchError(
            f"none of the default picks {picks!r} matched anything in the zip; use --pick"
        )

    combined: list[zipfile.ZipInfo] = []
    combined_ids = set()
    for m in picked + license_files:
        if id(m) not in combined_ids:
            combined_ids.add(id(m))
            combined.append(m)

    if not combined:
        raise FetchError("nothing selected to extract (empty --pick result and no license file)")
    if len(combined) > MAX_SELECTED_MEMBERS:
        raise FetchError(f"{len(combined)} members selected, over the {MAX_SELECTED_MEMBERS} cap")

    total_uncompressed = sum(m.file_size for m in combined)
    if total_uncompressed > MAX_SELECTED_UNCOMPRESSED_BYTES:
        raise FetchError(
            f"selected members total {total_uncompressed} uncompressed bytes, "
            f"over the {MAX_SELECTED_UNCOMPRESSED_BYTES} cap"
        )

    # Case-insensitive duplicate destination check (macOS is case-insensitive).
    seen_ci: dict[str, str] = {}
    for m in combined:
        dest = _validate_member_name(m.filename)
        key = dest.lower()
        if key in seen_ci and seen_ci[key] != dest:
            raise FetchError(
                f"case-insensitive duplicate destination: {seen_ci[key]!r} vs {dest!r}"
            )
        seen_ci[key] = dest

    return picked, license_files


def _license_sort_key(info: zipfile.ZipInfo) -> tuple[int, str]:
    path = info.filename
    return (path.count("/"), path)


def _is_readme(info: zipfile.ZipInfo) -> bool:
    return bool(
        re.match(r"^readme(?:[._\-].*)?$", posixpath.basename(info.filename), re.IGNORECASE)
    )


def classify_license_files(
    license_files: list[zipfile.ZipInfo],
) -> tuple[zipfile.ZipInfo | None, list[zipfile.ZipInfo]]:
    """Split the members matched by LICENSE_NAME_RE into (evidence, references).

    `evidence` is the file quoted as the pack's license text: an actual
    LICENSE/LICENCE/COPYRIGHT file, chosen deterministically (shallowest
    path, then lexicographic — never the zip's central directory order,
    which is an artifact of how the pack happened to be zipped) and
    always preferred over a README even if the README would otherwise
    sort first. A README is a preserved reference document, never
    license evidence: when the archive carries README(s) only, `evidence`
    is None and NOTHING is quoted as the license — the pack page's
    already-verified CC0 link remains the sole license evidence.

    `references` holds every other matched file (extra LICENSE-named
    files plus every README, sorted the same way) — all of them are
    still preserved on disk regardless, this only decides which ONE (if
    any) gets treated as license text."""
    named = sorted((i for i in license_files if not _is_readme(i)), key=_license_sort_key)
    readmes = sorted((i for i in license_files if _is_readme(i)), key=_license_sort_key)

    if named:
        evidence, references = named[0], named[1:] + readmes
    else:
        evidence, references = None, readmes
    references.sort(key=_license_sort_key)
    return evidence, references


def extract_selected(
    zf: zipfile.ZipFile, members: list[zipfile.ZipInfo], staging_dir: str
) -> list[tuple[str, str]]:
    """Extract members under staging_dir/assets/<archive-relative path>.
    Returns a list of (archive_path, output_path) pairs — archive_path is
    the zip member's own path, output_path is that same path prefixed with
    ASSETS_SUBDIR/ (staging_dir-relative), kept distinct in the return
    value and in provenance so a reader is never left guessing which one
    a given path is."""
    assets_root = os.path.join(staging_dir, ASSETS_SUBDIR)
    written: list[tuple[str, str]] = []
    for info in members:
        archive_path = _validate_member_name(info.filename)
        output_path = posixpath.join(ASSETS_SUBDIR, archive_path)
        dest_path = os.path.join(assets_root, *archive_path.split("/"))
        if os.path.islink(dest_path) or os.path.islink(os.path.dirname(dest_path)):
            raise FetchError(f"refusing to write through a symlink: {output_path}")
        os.makedirs(os.path.dirname(dest_path) or assets_root, exist_ok=True)
        try:
            with zf.open(info) as src, open(dest_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
        except zipfile.BadZipFile as exc:
            raise FetchError(f"corrupt zip (bad member {info.filename!r}): {exc}") from exc
        written.append((archive_path, output_path))
    return written


# ── output directory handling ────────────────────────────────────────────


def prepare_staging(out_dir: str) -> str:
    if os.path.islink(out_dir):
        raise FetchError(f"--out must not be a symlink: {out_dir}")
    if os.path.isdir(out_dir) and os.listdir(out_dir):
        raise FetchError(f"--out already exists and is non-empty: {out_dir}")
    if os.path.exists(out_dir) and not os.path.isdir(out_dir):
        raise FetchError(f"--out exists and is not a directory: {out_dir}")
    parent = os.path.dirname(os.path.abspath(out_dir)) or "."
    if not os.path.isdir(parent):
        raise FetchError(f"--out's parent directory does not exist: {parent}")
    staging = tempfile.mkdtemp(prefix=".kenney-fetch-", dir=parent)
    return staging


def publish_staging(staging_dir: str, out_dir: str) -> None:
    if os.path.isdir(out_dir):
        os.rmdir(out_dir)  # only reached when it existed and was empty
    os.rename(staging_dir, out_dir)


# ── pack fetch ────────────────────────────────────────────────────────────


def do_pack(slug: str, out_dir: str, picks: tuple[str, ...]) -> int:
    page_url, page = fetch_pack_page(slug)
    verify_cc0(page_url, page)
    zip_url = resolve_zip_url(page_url, page)

    staging = prepare_staging(out_dir)
    cleanup_staging = True
    tmp_zip_fd, tmp_zip_path = tempfile.mkstemp(
        prefix="kenney-fetch-", suffix=".zip", dir=os.path.dirname(staging)
    )
    os.close(tmp_zip_fd)
    try:
        sha256_hex, zip_bytes = _download_zip(zip_url, tmp_zip_path)
        zf = inspect_zip(tmp_zip_path)
        try:
            effective_picks = picks if picks else DEFAULT_PICKS
            picked, license_files = select_members(
                zf, effective_picks, require_each_match=bool(picks)
            )
            # An explicit --pick broad enough to also match a README/LICENSE
            # (e.g. --pick '*') puts the same member in both `picked` and
            # `license_files`; dedup before extracting so nothing is written
            # twice and selected_count/selected_files stay truthful.
            extraction_targets = _dedup_preserve_order(picked + license_files)
            written = extract_selected(zf, extraction_targets, staging)
        finally:
            zf.close()

        license_evidence, reference_docs = classify_license_files(license_files)

        license_text = None
        license_archive_path = None
        license_output_path = None
        if license_evidence is not None:
            with zipfile.ZipFile(tmp_zip_path) as zf2:
                license_archive_path = license_evidence.filename
                license_output_path = posixpath.join(ASSETS_SUBDIR, license_archive_path)
                license_text = zf2.read(license_evidence).decode("utf-8", errors="replace")

        reference_documents = [
            {
                "archive_path": info.filename,
                "output_path": posixpath.join(ASSETS_SUBDIR, info.filename),
            }
            for info in reference_docs
        ]

        provenance = {
            "tool": PROG,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pack": {"slug": slug, "title": page.title, "page_url": page_url},
            "zip": {"url": zip_url, "sha256": sha256_hex, "bytes": zip_bytes},
            "license": {
                "name": "CC0 1.0 Universal",
                "spdx": "CC0-1.0",
                "url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "verified_on_page": True,
                "archive_license_file": license_archive_path,
                "archive_license_file_output_path": license_output_path,
                "reference_documents": reference_documents,
            },
            "pick": list(picks) if picks else list(DEFAULT_PICKS),
            "pick_was_default": not bool(picks),
            "assets_dir": ASSETS_SUBDIR,
            "selected_count": len(written),
            "selected_files": [
                {"archive_path": archive_path, "output_path": output_path}
                for archive_path, output_path in sorted(written)
            ],
        }
        with open(os.path.join(staging, "provenance.json"), "w", encoding="utf-8") as fh:
            json.dump(provenance, fh, indent=2, sort_keys=False)
            fh.write("\n")

        if license_text:
            license_note = (
                f"Source archive license file (archive path: {license_archive_path}) "
                f"preserved at {license_output_path} under this pack's output "
                f"directory.\n\n{license_text}"
            )
        elif reference_documents:
            doc_lines = "\n".join(
                f"  - {d['archive_path']} (preserved at {d['output_path']})"
                for d in reference_documents
            )
            license_note = (
                "The archive carried no LICENSE/LICENCE/COPYRIGHT file — only "
                "reference document(s), preserved under this pack's output "
                "directory but NOT quoted as license text:\n"
                f"{doc_lines}\n\n"
                "The pack page's verified CC0 link (above) remains the sole "
                "license evidence.\n"
            )
        else:
            license_note = "The archive carried no separate license file; the pack page's CC0 link is the evidence.\n"
        with open(os.path.join(staging, "LICENSE.source.txt"), "w", encoding="utf-8") as fh:
            fh.write(
                f"{page.title or slug} — Creative Commons CC0 1.0 Universal (CC0-1.0)\n"
                f"https://creativecommons.org/publicdomain/zero/1.0/\n"
                f"Verified on: {page_url}\n"
                f"Zip: {zip_url}\n"
                f"Zip sha256: {sha256_hex}\n\n"
                f"{license_note}"
            )

        publish_staging(staging, out_dir)
        cleanup_staging = False
    finally:
        if os.path.exists(tmp_zip_path):
            os.remove(tmp_zip_path)
        if cleanup_staging and os.path.isdir(staging):
            shutil.rmtree(staging, ignore_errors=True)

    print(
        f"RESULT: pack={slug} title={page.title!r} out={os.path.abspath(out_dir)} "
        f"assets={os.path.join(os.path.abspath(out_dir), ASSETS_SUBDIR)} "
        f"files={len(written)} zip_sha256={sha256_hex} zip_bytes={zip_bytes}"
    )
    print(f"LICENSE: {page.title or slug} — CC0 1.0 Universal (CC0-1.0) https://creativecommons.org/publicdomain/zero/1.0/ (verified: {page_url})")
    return 0


# ── CLI ───────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG, description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--search", metavar="WORD", help="list candidate packs, write nothing")
    parser.add_argument("--pack", metavar="SLUG", help="the exact pack slug to fetch")
    parser.add_argument("--out", metavar="DIR", help="output directory (must not exist non-empty)")
    parser.add_argument(
        "--pick",
        metavar="GLOB",
        action="append",
        default=[],
        help="shell-style filename pattern (fnmatch — '*' matches '/' too, "
        "unlike a POSIX glob) against a zip member's path, repeatable "
        "(e.g. --pick 'PNG/Black/1x/arrow*.png'); default: *.png and "
        "*.svg everywhere",
    )
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.search:
            if args.pack or args.out or args.pick:
                raise FetchError("--search cannot be combined with --pack/--out/--pick")
            return do_search(args.search)
        if not args.pack:
            raise FetchError("either --search WORD or --pack SLUG --out DIR is required")
        if not args.out:
            raise FetchError("--pack requires --out DIR")
        return do_pack(args.pack, args.out, tuple(args.pick))
    except FetchError as exc:
        print(f"{PROG}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
