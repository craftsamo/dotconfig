"""archive_check: look inside a ZIP or tar archive before a messaging plugin sends it.

Shared by signal-access, whatsapp-access and telegram-access (each loads this file by path; it is
not a plugin and has no manifest). Nothing is ever extracted to disk: the archive is read in
memory, entry by entry, and refused as a whole at the first entry that would not be sent on its
own. An archive passes only when

* its name says zip / tar / tar.gz / tar.bz2 / tar.xz and its first bytes say the same (a ZIP named
  ``photo.jpg`` is not vetted here, so the caller's own "archive by content" refusal still applies);
* every entry has a plain relative name (no ``..``, no absolute path, no backslash), is a regular
  file or a folder (no links, devices or pipes) and, if it is a ZIP entry, is not encrypted;
* no entry sits in a keys-or-settings folder, is named like a key or secret file, is a program or
  script (by name, or by its first bytes: shebang, ELF, Mach-O, PE, Java class) or is itself an
  archive (nested archives are refused, by name and by first bytes);
* no entry contains a private key block anywhere in its content;
* there are at most ``MAX_ENTRIES`` entries and ``MAX_UNPACKED`` bytes once unpacked, counted from
  the bytes actually read, not from the sizes the archive claims.

Rar, 7z, zstd and the like are not readable with the standard library and stay refused by the
caller's name rule.
"""

from __future__ import annotations

import lzma
import re
import stat
import tarfile
import zipfile
import zlib
from pathlib import Path

MAX_ENTRIES = 500
MAX_UNPACKED = 500 * 1024 * 1024
CHUNK = 1 << 20
HEAD = 4096
PRIVATE_KEY = re.compile(rb"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
PRIVATE_KEY_OVERLAP = 64

# Archive family by name: the extensions that may be vetted at all.
NAME_FAMILY = (
    (re.compile(r"\.zip$", re.IGNORECASE), "zip"),
    (re.compile(r"\.tar$", re.IGNORECASE), "tar"),
    (re.compile(r"\.(?:tar\.gz|tgz)$", re.IGNORECASE), "gz"),
    (re.compile(r"\.(?:tar\.bz2|tbz2?)$", re.IGNORECASE), "bz2"),
    (re.compile(r"\.(?:tar\.xz|txz)$", re.IGNORECASE), "xz"),
)
TAR_MODE = {"tar": "r:", "gz": "r:gz", "bz2": "r:bz2", "xz": "r:xz"}
FORMAT_LABEL = {"zip": "zip", "tar": "tar", "gz": "tar.gz", "bz2": "tar.bz2", "xz": "tar.xz"}

MACHO = {b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",
         b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}


class ArchiveRefused(Exception):
    """The archive (or something in it) may not be sent; the message says why."""


def family_of_name(name: str) -> str | None:
    """zip / tar / gz / bz2 / xz when the name is one the vetting reads, else None."""
    for pattern, family in NAME_FAMILY:
        if pattern.search(name or ""):
            return family
    return None


def family_of_head(head: bytes) -> str | None:
    if head[:4] in (b"PK\x03\x04", b"PK\x05\x06"):
        return "zip"
    if head[:2] == b"\x1f\x8b":
        return "gz"
    if head[:3] == b"BZh" and head[3:4].isdigit():
        return "bz2"
    if head[:6] == b"\xfd7zXZ\x00":
        return "xz"
    if head[257:262] == b"ustar":
        return "tar"
    return None


def _refusal_by_head(head: bytes) -> str | None:
    """What an entry's first bytes give away: a program, a script or another archive."""
    if head[:2] == b"#!":
        return "a script"
    if head[:4] == b"\x7fELF" or head[:4] in MACHO:
        return "a program"
    if head[:2] == b"MZ" and len(head) >= 0x40:
        offset = int.from_bytes(head[0x3C:0x40], "little")
        if offset + 4 <= len(head) and head[offset:offset + 4] == b"PE\x00\x00":
            return "a program"
    if family_of_head(head) is not None or head[:4] == b"7z\xbc\xaf" or head[:4] == b"Rar!":
        return "an archive inside the archive"
    return None


class _Budget:
    def __init__(self):
        self.entries = 0
        self.files = 0
        self.unpacked = 0

    def entry(self) -> None:
        self.entries += 1
        if self.entries > MAX_ENTRIES:
            raise ArchiveRefused(f"it has more than {MAX_ENTRIES} entries")

    def take(self, size: int) -> None:
        self.unpacked += size
        if self.unpacked > MAX_UNPACKED:
            raise ArchiveRefused(f"it unpacks to more than {MAX_UNPACKED // (1024 * 1024)} MB")


def _entry_path(raw: str) -> list[str]:
    if not raw or "\x00" in raw or "\\" in raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise ArchiveRefused(f"{raw!r} is not a plain relative path")
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if not parts or ".." in parts:
        raise ArchiveRefused(f"{raw!r} is not a plain relative path")
    return parts


def _check_name(raw: str, is_dir: bool, deny_parts, deny_names, risky_files) -> None:
    parts = _entry_path(raw)
    folders = parts if is_dir else parts[:-1]
    if {p.lower() for p in folders} & deny_parts:
        raise ArchiveRefused(f"{raw!r} is in a place for keys or settings")
    if is_dir:
        return
    name = parts[-1]
    if deny_names.match(name):
        raise ArchiveRefused(f"{raw!r} is named like a key or secret file")
    if risky_files.search(name):
        raise ArchiveRefused(f"{raw!r} is an archive or a program")


def _scan(stream, raw: str, budget: _Budget) -> None:
    """Read one entry to its end: first bytes, private keys, and the bytes counted."""
    first, tail, size = True, b"", 0
    while True:
        chunk = stream.read(CHUNK)
        if not chunk:
            break
        if first:
            first = False
            why = _refusal_by_head(chunk[:HEAD])
            if why:
                raise ArchiveRefused(f"{raw!r} is {why}")
        size += len(chunk)
        budget.take(len(chunk))
        if PRIVATE_KEY.search(tail + chunk):
            raise ArchiveRefused(f"{raw!r} contains a private key")
        tail = chunk[-PRIVATE_KEY_OVERLAP:]
    if size:
        budget.files += 1


def _walk_zip(path: Path, budget: _Budget, checks) -> None:
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ArchiveRefused(f"it has more than {MAX_ENTRIES} entries")
        if sum(i.file_size for i in infos) > MAX_UNPACKED:
            raise ArchiveRefused(f"it unpacks to more than {MAX_UNPACKED // (1024 * 1024)} MB")
        for info in infos:
            budget.entry()
            is_dir = info.is_dir()
            _check_name(info.filename, is_dir, *checks)
            kind = stat.S_IFMT(info.external_attr >> 16)  # 0 when the archiver stored no file type
            if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ArchiveRefused(f"{info.filename!r} is a link or a special file")
            if info.flag_bits & 0x1:
                raise ArchiveRefused(f"{info.filename!r} is encrypted, so it cannot be checked")
            if not is_dir:
                with archive.open(info) as stream:
                    _scan(stream, info.filename, budget)


def _walk_tar(path: Path, family: str, budget: _Budget, checks) -> None:
    with tarfile.open(path, TAR_MODE[family]) as archive:
        for member in archive:
            budget.entry()
            if not (member.isreg() or member.isdir()):
                raise ArchiveRefused(f"{member.name!r} is a link or a special file")
            _check_name(member.name, member.isdir(), *checks)
            if member.isreg():
                if budget.unpacked + member.size > MAX_UNPACKED:
                    raise ArchiveRefused(f"it unpacks to more than {MAX_UNPACKED // (1024 * 1024)} MB")
                stream = archive.extractfile(member)
                if stream is not None:
                    _scan(stream, member.name, budget)


def vet(path: Path, name: str, *, deny_parts, deny_names, risky_files) -> dict | None:
    """None when ``name`` is not an archive this module reads (the caller's own rules decide).
    Otherwise the archive is inspected: ``{"format", "entries", "unpacked"}`` when it may be sent,
    ArchiveRefused when it may not.

    ``deny_parts`` (lower-case folder names), ``deny_names`` (a regex, ``.match`` on a file name)
    and ``risky_files`` (a regex, ``.search`` on a file name: archives, installers, programs and
    scripts) are the caller's own rules for single files, applied to every entry."""
    family = family_of_name(name)
    if family is None:
        return None
    try:
        with open(path, "rb") as handle:
            head = handle.read(512)
        if family_of_head(head) != family:
            raise ArchiveRefused(f"its content is not a {FORMAT_LABEL[family]} archive, whatever the name says")
        budget = _Budget()
        checks = (deny_parts, deny_names, risky_files)
        if family == "zip":
            _walk_zip(path, budget, checks)
        else:
            _walk_tar(path, family, budget, checks)
    except ArchiveRefused:
        raise
    except (zipfile.BadZipFile, tarfile.TarError, EOFError, OSError, zlib.error, lzma.LZMAError,
            RuntimeError, NotImplementedError, ValueError, OverflowError) as exc:
        raise ArchiveRefused(f"it cannot be read as an archive ({exc.__class__.__name__})") from exc
    if budget.files == 0:
        raise ArchiveRefused("it contains no files")
    return {"format": FORMAT_LABEL[family], "entries": budget.files, "unpacked": budget.unpacked}
