"""Unpacking a received archive, and the terminal guard that keeps what is inside from being run."""

import importlib.util
import io
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
import zipfile

import pytest

spec = importlib.util.spec_from_file_location("archive_check_unpack_under_test",
                                              Path(__file__).resolve().parent.parent / "archive_check.py")
ac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ac)

RISKY = re.compile(r"\.(?:zip|rar|7z|tar|gz|tgz|exe|jar|msi|dmg|app|command|sh|py|js|bat)$", re.IGNORECASE)


def make_zip(path, entries, mode=None):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name)
            if mode is not None:
                info.external_attr = mode << 16
            z.writestr(info, data)
    return path


def unpack(path, dest, only=None):
    return ac.extract(path, path.name, dest, risky_files=RISKY, only=only)


GOOD = {"notes.txt": b"hello", "data/q1.csv": b"a,b\n1,2\n", "src/run.sh": b"#!/bin/sh\necho hi\n"}


def leftovers(folder):
    return [p.name for p in folder.iterdir() if p.name.startswith(".unpacking-")]


def test_everything_is_written_without_an_execute_bit_and_the_archive_is_left_alone(tmp_path):
    archive = make_zip(tmp_path / "pack.zip", GOOD, mode=0o755)         # the sender asked for executable files
    before = archive.read_bytes()
    out = unpack(archive, tmp_path / "pack.unpacked")
    folder = Path(out["folder"])
    assert folder == tmp_path / "pack.unpacked" and out["count"] == 3 and out["more"] == 0
    assert sorted(out["files"]) == ["data/q1.csv", "notes.txt", "src/run.sh"]
    assert (folder / "data" / "q1.csv").read_bytes() == b"a,b\n1,2\n"
    for path in folder.rglob("*"):
        mode = stat.S_IMODE(path.stat().st_mode)
        assert not mode & 0o111 if path.is_file() else mode == 0o755
    assert archive.read_bytes() == before and leftovers(tmp_path) == []


@pytest.mark.skipif(sys.platform != "darwin", reason="the quarantine flag is macOS's")
def test_every_unpacked_file_is_marked_as_downloaded(tmp_path):
    out = unpack(make_zip(tmp_path / "pack.zip", GOOD), tmp_path / "pack.unpacked")
    for rel in out["files"]:
        flag = subprocess.run(["/usr/bin/xattr", "-p", "com.apple.quarantine", str(Path(out["folder"]) / rel)],
                              capture_output=True, text=True).stdout
        assert flag.startswith("0081;"), rel


@pytest.mark.parametrize("name,mode", [("a.tar", "w:"), ("a.tar.gz", "w:gz"), ("a.tar.bz2", "w:bz2"),
                                        ("a.tar.xz", "w:xz")])
def test_tar_archives_unpack_too(tmp_path, name, mode):
    path = tmp_path / name
    with tarfile.open(path, mode) as t:
        for entry, data in GOOD.items():
            info = tarfile.TarInfo(entry)
            info.size = len(data)
            info.mode = 0o755
            t.addfile(info, io.BytesIO(data))
    out = unpack(path, tmp_path / "t.unpacked")
    assert out["count"] == 3 and not stat.S_IMODE((Path(out["folder"]) / "src" / "run.sh").stat().st_mode) & 0o111


def test_only_the_named_entries_and_folders_are_unpacked(tmp_path):
    archive = make_zip(tmp_path / "pack.zip", GOOD)
    out = unpack(archive, tmp_path / "p.unpacked", only=["notes.txt", "data"])
    assert sorted(out["files"]) == ["data/q1.csv", "notes.txt"]
    assert not (Path(out["folder"]) / "src").exists()
    with pytest.raises(ac.ArchiveRefused, match="no entry named 'missing.txt'"):
        unpack(archive, tmp_path / "q.unpacked", only=["notes.txt", "missing.txt"])
    assert not (tmp_path / "q.unpacked").exists() and leftovers(tmp_path) == []


@pytest.mark.parametrize("entries, fragment", [
    ({"../evil.txt": b"x", "a.txt": b"y"}, "not a plain relative path"),
    ({"/etc/evil.txt": b"x", "a.txt": b"y"}, "not a plain relative path"),
    ({"setup.exe": b"x", "a.txt": b"y"}, "an archive or a program"),
    ({"a.txt": b"\x7fELF\x02\x01\x01" + b"\x00" * 60}, "a program"),
    ({"inner.zip": b"x", "a.txt": b"y"}, "an archive or a program"),
])
def test_a_hostile_archive_writes_nothing(tmp_path, entries, fragment):
    with pytest.raises(ac.ArchiveRefused, match=fragment):
        unpack(make_zip(tmp_path / "bad.zip", entries), tmp_path / "bad.unpacked")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bad.zip"]


def test_a_link_in_the_archive_writes_nothing(tmp_path):
    path = tmp_path / "bad.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("a.txt", "x")
        link = zipfile.ZipInfo("link.txt")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        z.writestr(link, "/etc/passwd")
    with pytest.raises(ac.ArchiveRefused, match="link or a special file"):
        unpack(path, tmp_path / "bad.unpacked")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bad.zip"]


def test_the_saved_archive_must_be_a_plain_file_not_a_link(tmp_path):
    real = make_zip(tmp_path / "real.zip", GOOD)
    link = tmp_path / "link.zip"
    os.symlink(real, link)
    with pytest.raises(ac.ArchiveRefused, match="cannot be read"):
        unpack(link, tmp_path / "l.unpacked")
    assert leftovers(tmp_path) == []


@pytest.mark.filterwarnings("ignore:Duplicate name")
def test_names_that_clash_are_numbered_not_overwritten(tmp_path):
    path = tmp_path / "dup.zip"          # a ZIP may hold one name twice
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("dup.txt", "first")
        z.writestr("dup.txt", "second")
        z.writestr("Case.txt", "upper")
        z.writestr("case.txt", "lower")
    out = unpack(path, tmp_path / "d.unpacked")
    folder = Path(out["folder"])
    assert out["count"] == 4
    assert (folder / "dup.txt").read_text() == "first" and (folder / "dup-2.txt").read_text() == "second"
    assert sorted(p.read_text() for p in folder.glob("[Cc]ase*")) == ["lower", "upper"]


def test_a_file_and_a_folder_with_one_name_clash_and_nothing_is_kept(tmp_path):
    path = tmp_path / "bad.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("a", "file")
        z.writestr("a/b.txt", "inside")
    with pytest.raises(ac.ArchiveRefused, match="clashing names"):
        unpack(path, tmp_path / "bad.unpacked")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bad.zip"]


def test_odd_characters_in_names_are_replaced_on_disk(tmp_path):
    out = unpack(make_zip(tmp_path / "odd.zip", {"two\nlines\u202e.txt": b"x", "ok.txt": b"y"}),
                 tmp_path / "o.unpacked")
    names = sorted(p.name for p in Path(out["folder"]).iterdir())
    assert names == ["ok.txt", "two_lines_.txt"]


def test_a_taken_destination_gets_a_numbered_folder(tmp_path):
    archive = make_zip(tmp_path / "pack.zip", GOOD)
    first = unpack(archive, tmp_path / "pack.unpacked")
    second = unpack(archive, tmp_path / "pack.unpacked")
    assert Path(first["folder"]).name == "pack.unpacked" and Path(second["folder"]).name == "pack-2.unpacked"
    assert (Path(first["folder"]) / "notes.txt").exists()


def test_a_bomb_is_refused_before_anything_is_written(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "MAX_UNPACKED", 1024 * 1024)
    with pytest.raises(ac.ArchiveRefused, match="unpacks to more than"):
        unpack(make_zip(tmp_path / "bomb.zip", {"zeros.txt": b"\x00" * (4 * 1024 * 1024)}), tmp_path / "b.unpacked")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bomb.zip"]


def test_a_long_listing_is_cut_and_counted(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "LISTING_MAX", 3)
    out = unpack(make_zip(tmp_path / "many.zip", {f"f{i}.txt": b"x" for i in range(7)}), tmp_path / "m.unpacked")
    assert out["count"] == 7 and len(out["files"]) == 3 and out["more"] == 4


# --- the guard ------------------------------------------------------------------------------------------

UP = "~/Workspaces/.inbox/signal/chat-1/pack.unpacked"


def guard(command, workdir=None):
    args = {"command": command}
    if workdir:
        args["workdir"] = workdir
    return ac.unpacked_guard("terminal", args)


@pytest.mark.parametrize("command", [
    f"bash {UP}/run.sh",
    f"sh -x {UP}/run.sh arg",
    f"python3 {UP}/tool.py",
    f"python -u {UP}/tool.py",
    f"{UP}/bin/tool",
    f"./{UP}/run.sh",
    f"node {UP}/app.js",
    f"ruby {UP}/job.rb",
    f"java -jar {UP}/app.jar",
    f"source {UP}/env.sh",
    f". {UP}/env.sh",
    f"env FOO=1 python {UP}/x.py",
    f"sudo bash {UP}/run.sh",
    f"nohup python {UP}/x.py &",
    f"cd {UP} && ./run.sh",
    f"cd {UP} && python tool.py",
    f"cd {UP}; bash run.sh",
    f"cd {UP} && make",
    f"cd {UP} && npm install",
    f"open {UP}/Tool.app",
    f"open -a Terminal {UP}/x",
    f"chmod +x {UP}/run.sh",
    f"chmod 755 {UP}/run.sh",
    f"xattr -d com.apple.quarantine {UP}/run.sh",
    f"xattr -cr {UP}",
    f"find {UP} -name '*.sh' -exec bash {{}} \\;",
    f"ls {UP} | xargs bash",
    f"make -C {UP}",
    f"npm install --prefix {UP}",
    f"bash -c 'cd {UP} && ./run.sh'",
    f"python3 -c \"exec(open('{UP}/x.py').read())\"",
    f"echo hi && python3 {UP}/tool.py",
])
def test_running_what_was_received_is_blocked(command):
    assert guard(command) == ac.RUN_MESSAGE


def test_the_working_folder_counts(tmp_path):
    inside = "/Users/x/Workspaces/.inbox/telegram/9-1/pack.unpacked/sub"
    assert guard("./run.sh", inside) == ac.RUN_MESSAGE
    assert guard("python tool.py", inside) == ac.RUN_MESSAGE
    assert guard("cat notes.txt", inside) is None and guard("ls -la", inside) is None


@pytest.mark.parametrize("command", [
    f"cat {UP}/notes.txt",
    f"head -50 {UP}/data/q1.csv",
    f"ls -la {UP}",
    f"grep -rn invoice {UP}",
    f"jq . {UP}/data.json",
    f"file {UP}/*",
    f"wc -l {UP}/data/q1.csv",
    f"python analyze.py {UP}/data/q1.csv",
    f"python3 ~/Workspaces/tools/summarise.py --input {UP}/data.csv",
    f"python3 -m json.tool {UP}/data.json",
    f"python3 -c \"import csv; print(sum(1 for _ in csv.reader(open('{UP}/data.csv'))))\"",
    f"cd {UP} && ls && cat notes.txt",
    f"cd {UP} && cat run.sh | head -5",
    f"sqlite3 {UP}/db.sqlite 'select count(*) from t'",
    f"cp {UP}/report.pdf ~/Workspaces/out/",
    f"open -R {UP}/report.pdf",
    f"rm -rf {UP}",
    f"cat {UP}/list.txt | xargs grep -l foo",
    "python tool.py",                     # nothing to do with an unpacked folder
    "./run.sh",
])
def test_reading_and_analysing_what_was_received_is_not_blocked(command):
    assert guard(command) is None


def test_only_the_terminal_is_guarded_and_an_unparsable_command_does_not_crash():
    assert ac.unpacked_guard("read_file", {"path": f"{UP}/run.sh"}) is None
    assert ac.unpacked_guard("terminal", "not a dict") is None
    assert ac.unpacked_guard("terminal", {"command": f"echo 'unbalanced {UP}"}) is None
    assert ac.unpacked_guard("terminal", {"command": f"bash 'unbalanced {UP}/x.sh"}) == ac.RUN_MESSAGE
