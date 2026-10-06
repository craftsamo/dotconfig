"""archive_check against archives built in a temporary folder; nothing outside it is touched."""

import importlib.util
import io
import os
from pathlib import Path
import re
import struct
import tarfile
import zipfile

import pytest

spec = importlib.util.spec_from_file_location("archive_check_under_test",
                                              Path(__file__).resolve().parent.parent / "archive_check.py")
ac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ac)

DENY_PARTS = {".ssh", ".git", ".config"}
DENY_NAMES = re.compile(r"^(?:\.env.*|.*secret.*|.*\.(?:pem|key))$", re.IGNORECASE)
RISKY = re.compile(r"\.(?:zip|rar|7z|tar|gz|tgz|exe|jar|sh|py|js|app)$", re.IGNORECASE)
RULES = dict(deny_parts=DENY_PARTS, deny_names=DENY_NAMES, risky_files=RISKY)


def make_zip(path, entries, method=zipfile.ZIP_DEFLATED):
    with zipfile.ZipFile(path, "w", method) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return path


def make_tar(path, entries, mode="w:"):
    with tarfile.open(path, mode) as t:
        for name, data in entries.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return path


def vet(path):
    return ac.vet(path, path.name, **RULES)


def refused(path, fragment):
    with pytest.raises(ac.ArchiveRefused) as err:
        vet(path)
    assert fragment in str(err.value)


GOOD = {"notes/a.txt": b"hello\n", "notes/b.csv": b"1,2\n3,4\n", "img/p.png": b"\x89PNG\r\n\x1a\nxxxx"}


def test_plain_zip_passes_with_counts(tmp_path):
    info = vet(make_zip(tmp_path / "docs.zip", GOOD))
    assert info == {"format": "zip", "entries": 3, "unpacked": sum(len(v) for v in GOOD.values())}


@pytest.mark.parametrize("name,mode,label", [("a.tar", "w:", "tar"), ("a.tar.gz", "w:gz", "tar.gz"),
                                              ("a.tgz", "w:gz", "tar.gz"), ("a.tar.bz2", "w:bz2", "tar.bz2"),
                                              ("a.tar.xz", "w:xz", "tar.xz")])
def test_tar_families_pass(tmp_path, name, mode, label):
    info = vet(make_tar(tmp_path / name, GOOD, mode))
    assert info["format"] == label and info["entries"] == 3


def test_names_that_are_not_readable_archives_are_left_to_the_caller(tmp_path):
    for name in ("a.rar", "a.7z", "a.gz", "a.jar", "a.txt", "a.docx"):
        assert ac.vet(tmp_path / name, name, **RULES) is None


def test_disguised_and_mismatched_content_is_refused(tmp_path):
    zipped = make_zip(tmp_path / "x.zip", GOOD)
    (tmp_path / "pic.zip").write_bytes(b"\xff\xd8\xff\xe0" + zipped.read_bytes())
    refused(tmp_path / "pic.zip", "not a zip archive")
    (tmp_path / "fake.zip").write_text("just text, not an archive")
    refused(tmp_path / "fake.zip", "not a zip archive")
    gz = make_tar(tmp_path / "real.tar.gz", GOOD, "w:gz")
    (tmp_path / "wrong.tar.xz").write_bytes(gz.read_bytes())
    refused(tmp_path / "wrong.tar.xz", "not a tar.xz archive")
    (tmp_path / "plain.tar.gz").write_bytes(b"\x1f\x8b\x08\x00 not really gzip")
    refused(tmp_path / "plain.tar.gz", "cannot be read as an archive")


@pytest.mark.parametrize("entries,fragment", [
    ({".env": b"A=1\n"}, "named like a key or secret"),
    ({"proj/.ssh/config": b"Host x\n"}, "keys or settings"),
    ({".git/HEAD": b"ref\n"}, "keys or settings"),
    ({"keys/server.pem": b"x"}, "named like a key or secret"),
    ({"my-secret-plan.txt": b"x"}, "named like a key or secret"),
    ({"run.sh": b"echo hi\n"}, "an archive or a program"),
    ({"tool.py": b"print(1)\n"}, "an archive or a program"),
    ({"inner.zip": b"x"}, "an archive or a program"),
    ({"lib.jar": b"x"}, "an archive or a program"),
    ({"../evil.txt": b"x"}, "not a plain relative path"),
    ({"/etc/evil.txt": b"x"}, "not a plain relative path"),
    ({"a\\b.txt": b"x"}, "not a plain relative path"),
    ({"C:evil.txt": b"x"}, "not a plain relative path"),
    ({"a/../../b.txt": b"x"}, "not a plain relative path"),
])
def test_zip_entries_that_would_be_refused_alone(tmp_path, entries, fragment):
    refused(make_zip(tmp_path / "x.zip", {**GOOD, **entries}), fragment)


@pytest.mark.parametrize("data,fragment", [
    (b"#!/bin/sh\necho hi\n", "a script"),
    (b"\x7fELF\x02\x01\x01" + b"\x00" * 60, "a program"),
    (b"\xcf\xfa\xed\xfe" + b"\x00" * 60, "a program"),
    (b"\xca\xfe\xba\xbe\x00\x00\x00\x34", "a program"),
    (b"MZ" + b"\x00" * 58 + struct.pack("<I", 0x80) + b"\x00" * 64 + b"PE\x00\x00", "a program"),
    (b"PK\x03\x04" + b"\x00" * 30, "an archive inside the archive"),
    (b"\x1f\x8b\x08\x00" + b"\x00" * 30, "an archive inside the archive"),
    (b"7z\xbc\xaf\x27\x1c" + b"\x00" * 30, "an archive inside the archive"),
    (b"Rar!\x1a\x07\x00" + b"\x00" * 30, "an archive inside the archive"),
    (b"notes\n-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n", "contains a private key"),
])
def test_entries_given_away_by_their_content(tmp_path, data, fragment):
    refused(make_zip(tmp_path / "x.zip", {**GOOD, "innocent.txt": data}), fragment)


def test_private_key_across_a_read_boundary_is_found(tmp_path):
    data = b"a" * (ac.CHUNK - 10) + b"-----BEGIN RSA PRIVATE KEY-----\n" + b"b" * 100
    refused(make_zip(tmp_path / "x.zip", {"big.txt": data}), "contains a private key")


def test_text_that_merely_starts_like_a_program_is_fine(tmp_path):
    assert vet(make_zip(tmp_path / "x.zip", {"a.txt": b"MZ station list\n", "b.txt": b"BZh is not bzip2\n"}))


def test_encrypted_zip_entry_is_refused(tmp_path):
    path = make_zip(tmp_path / "x.zip", GOOD)
    raw = bytearray(path.read_bytes())
    flags = [m.start() for m in re.finditer(rb"PK\x01\x02", bytes(raw))]
    for at in flags + [m.start() for m in re.finditer(rb"PK\x03\x04", bytes(raw))]:
        offset = at + (8 if raw[at + 2:at + 4] == b"\x01\x02" else 6)
        raw[offset] |= 0x1
    path.write_bytes(bytes(raw))
    refused(path, "cannot be")


def test_zip_symlink_entry_is_refused(tmp_path):
    path = tmp_path / "x.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("ok.txt", "x")
        link = zipfile.ZipInfo("link.txt")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        z.writestr(link, "/etc/passwd")
    refused(path, "link or a special file")


def test_tar_links_and_devices_are_refused(tmp_path):
    for kind, fields in ((tarfile.SYMTYPE, {"linkname": "/etc/passwd"}), (tarfile.LNKTYPE, {"linkname": "a.txt"}),
                         (tarfile.FIFOTYPE, {}), (tarfile.CHRTYPE, {})):
        path = tmp_path / f"t{ord(kind)}.tar"
        with tarfile.open(path, "w") as t:
            ok = tarfile.TarInfo("a.txt")
            ok.size = 2
            t.addfile(ok, io.BytesIO(b"hi"))
            odd = tarfile.TarInfo("odd")
            odd.type = kind
            for key, value in fields.items():
                setattr(odd, key, value)
            t.addfile(odd)
        refused(path, "link or a special file")


def test_tar_path_traversal_is_refused(tmp_path):
    refused(make_tar(tmp_path / "x.tar", {"../x.txt": b"x", **GOOD}), "not a plain relative path")


def test_too_many_entries_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "MAX_ENTRIES", 5)
    refused(make_zip(tmp_path / "x.zip", {f"f{i}.txt": b"x" for i in range(6)}), "more than 5 entries")
    refused(make_tar(tmp_path / "x.tar", {f"f{i}.txt": b"x" for i in range(6)}), "more than 5 entries")


def test_unpacked_size_is_counted_from_what_is_read(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "MAX_UNPACKED", 1024 * 1024)
    refused(make_zip(tmp_path / "bomb.zip", {"zeros.txt": b"\x00" * (4 * 1024 * 1024)}), "unpacks to more than")
    refused(make_tar(tmp_path / "bomb.tar.gz", {"zeros.txt": b"\x00" * (4 * 1024 * 1024)}, "w:gz"),
            "unpacks to more than")


def test_a_zip_that_lies_about_its_sizes_is_still_counted(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "MAX_UNPACKED", 1024 * 1024)
    path = make_zip(tmp_path / "x.zip", {"zeros.txt": b"\x00" * (4 * 1024 * 1024)})
    raw = bytearray(path.read_bytes())
    # shrink the uncompressed size claimed in the central directory and the local header
    for signature, at in ((b"PK\x01\x02", 24), (b"PK\x03\x04", 22)):
        start = bytes(raw).index(signature)
        raw[start + at:start + at + 4] = struct.pack("<I", 100)
    path.write_bytes(bytes(raw))
    with pytest.raises(ac.ArchiveRefused):
        vet(path)


def test_archive_without_files_is_refused(tmp_path):
    refused(make_zip(tmp_path / "empty.zip", {}), "no files")
    refused(make_zip(tmp_path / "dirs.zip", {"a/": b"", "a/b/": b""}), "no files")
    refused(make_tar(tmp_path / "empty.tar", {}), "not a tar archive")
    path = tmp_path / "dirs.tar"
    with tarfile.open(path, "w") as t:
        folder = tarfile.TarInfo("a")
        folder.type = tarfile.DIRTYPE
        t.addfile(folder)
    refused(path, "no files")


def test_folders_and_dot_prefixed_names_are_fine(tmp_path):
    assert vet(make_zip(tmp_path / "x.zip", {"./a/": b"", "./a/b.txt": b"x", "__MACOSX/a/._b.txt": b"y"}))["entries"] == 2


def test_a_missing_file_is_a_refusal_not_a_crash(tmp_path):
    refused(tmp_path / "gone.zip", "cannot be read as an archive")
