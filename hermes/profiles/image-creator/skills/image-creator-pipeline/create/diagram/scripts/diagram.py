#!/usr/bin/env python3
"""Check and render one self-contained HTML+inline-SVG diagram offline. No generation, no network."""

import argparse
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

REMOTE = re.compile(r"(?:https?:)?//", re.I)
URL_FUNCTION = re.compile(r"url\(\s*(['\"]?)\s*([^)'\"]*)", re.I)
IMPORT = re.compile(r"@import", re.I)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def norm(value):
    return re.sub(r"\s+", " ", value).strip()


def command(argv, **kwargs):
    proc = subprocess.run([str(v) for v in argv], capture_output=True, timeout=90, **kwargs)
    require(proc.returncode == 0, f"{argv[0]} failed: {proc.stderr.decode(errors='replace')[:1500]}")
    return proc.stdout


def write(path, data):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2) + "\n")


class Inspect(HTMLParser):
    """Collects self-containment violations and the text content of every SVG <text>/<tspan>."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.problems, self.texts = [], []
        self.stack, self.style, self.in_svg = [], False, 0

    def css(self, value, where):
        if IMPORT.search(value):
            self.problems.append(f"{where}: @import")
        for _, target in URL_FUNCTION.findall(value):
            if not (target.startswith("data:") or target.startswith("#")):
                self.problems.append(f"{where}: url({target[:60]})")

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.problems.append("<script> element")
        if tag == "link" and "stylesheet" in (dict(attrs).get("rel") or "").lower():
            self.problems.append("<link rel=stylesheet>")
        if tag in ("iframe", "object", "embed"):
            self.problems.append(f"<{tag}> element")
        for key, value in attrs:
            value = value or ""
            if key == "style":
                self.css(value, "style attribute")
            if key in ("src", "href", "xlink:href"):
                if REMOTE.match(value.strip()):
                    self.problems.append(f"remote {key}: {value[:60]}")
                elif tag in ("image", "img") and not value.strip().startswith("data:"):
                    self.problems.append(f"external <{tag}> {key}: {value[:60]}")
        if tag == "style":
            self.style = True
        if tag == "svg":
            self.in_svg += 1
        if tag in ("text", "tspan") and self.in_svg:
            self.stack.append(tag)
            if tag == "text":
                self.texts.append("")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "style":
            self.style = False
        if tag == "svg" and self.in_svg:
            self.in_svg -= 1
        if tag in ("text", "tspan") and self.stack and self.stack[-1] == tag:
            self.stack.pop()

    def handle_data(self, data):
        if self.style:
            self.css(data, "<style>")
        elif self.stack and self.texts:
            self.texts[-1] += data


def inspect(html_path, labels_path):
    source = html_path.read_text(encoding="utf-8")
    parser = Inspect()
    parser.feed(source)
    parser.close()
    require(not parser.problems, "HTML is not self-contained: " + "; ".join(parser.problems))
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    require(isinstance(labels, list) and labels and all(isinstance(v, str) and v.strip() for v in labels),
            "labels.json must be a non-empty JSON array of non-empty strings")
    texts = [norm(t) for t in parser.texts]
    missing = [label for label in labels if norm(label) not in texts and not any(norm(label) in t for t in texts)]
    require(not missing, "labels missing from the SVG text: " + " | ".join(missing))
    return {"self_contained": True, "labels_ok": True, "labels": len(labels), "svg_text_elements": len(texts)}


def measure(path):
    w, h = command(["magick", "identify", "-format", "%w %h", path]).decode().split()
    return [int(w), int(h)]


def render(html_path, size, work, out):
    """1x: two screenshots at device scale 1. 2x: the same page re-laid at device scale factor 2,
    two screenshots. Each pair must be byte-identical (RGBA)."""
    width, height = size
    session = "diagram-" + uuid.uuid4().hex[:16]
    write(work / "browser.json", {"headed": False, "restoreSave": "never"})
    argv = ["agent-browser", "--config", str(work / "browser.json"), "--namespace", session, "--session", session, "--json"]
    env = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR", "LANG") if k in os.environ}
    env.update({"DO_NOT_TRACK": "1", "AGENT_BROWSER_IDLE_TIMEOUT_MS": "20000"})

    def call(*args, script=None):
        raw = command(argv + list(args), cwd=work, env=env, input=script.encode() if script else None)
        data = json.loads(raw)
        require(data.get("success") is True, "browser rejected command: " + str(data))
        return data.get("data", {})

    settle = "new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(true))))"
    try:
        call("open", "about:blank")
        call("set", "offline", "on")
        call("set", "viewport", str(width), str(height), "1")
        call("open", html_path.as_uri())
        call("eval", "--stdin", script="document.fonts.ready.then(()=>true)")
        shots = {}
        for scale, suffix in ((1, ""), (2, "@2x")):
            if scale == 2:
                call("set", "viewport", str(width), str(height), "2")
            call("eval", "--stdin", script=settle)
            call("screenshot", str(work / f"a{suffix}.png"))
            call("eval", "--stdin", script=settle)
            call("screenshot", str(work / f"b{suffix}.png"))
            shots[suffix] = (work / f"a{suffix}.png", work / f"b{suffix}.png")
        errors = call("errors")
        require(not errors.get("errors"), "browser page errors: " + json.dumps(errors.get("errors"))[:500])
    finally:
        call("close")
    for suffix, (a, b) in shots.items():
        pa, pb = (command(["magick", p, "-depth", "8", "rgba:-"]) for p in (a, b))
        require(pa == pb, f"unstable render at {suffix or '1x'}; nothing published")
    command(["magick", shots[""][0], "-strip", out / "diagram.png"])
    command(["magick", shots["@2x"][0], "-strip", out / "diagram@2x.png"])
    sizes = {"diagram.png": measure(out / "diagram.png"), "diagram@2x.png": measure(out / "diagram@2x.png")}
    require(sizes["diagram.png"] == [width, height], f"1x render is {sizes['diagram.png']}, expected {[width, height]}")
    require(sizes["diagram@2x.png"] == [width * 2, height * 2], f"2x render is {sizes['diagram@2x.png']}, expected {[width * 2, height * 2]}")
    command(["magick", "(", out / "diagram.png", "-resize", "800x", ")", "(", out / "diagram.png", "-resize", "400x", ")",
             "-background", "#888888", "-gravity", "north", "+append", "-strip", out / "sheet.png"])
    sizes["sheet.png"] = measure(out / "sheet.png")
    return sizes


def parse_size(value):
    match = re.fullmatch(r"([1-9][0-9]{1,3})x([1-9][0-9]{1,3})", value)
    require(match, "--size must be WIDTHxHEIGHT, 10..9999 each")
    width, height = int(match[1]), int(match[2])
    require(64 <= width <= 4096 and 64 <= height <= 4096, "--size must be 64..4096 per side")
    return width, height


def run_render(args):
    html_path, labels_path = args.html.resolve(), args.labels.resolve()
    require(html_path.is_file(), "--html must be an existing file")
    require(labels_path.is_file(), "--labels must be an existing file")
    require(not args.out.exists() and not args.out.is_symlink(), "output already exists; choose a fresh directory")
    require(args.out.parent.is_dir(), "--out needs an existing parent directory")
    size = parse_size(args.size)
    checks = inspect(html_path, labels_path)
    out = args.out.resolve()
    out.mkdir()
    work = Path(tempfile.mkdtemp(prefix=".work-", dir=out))
    try:
        sizes = render(html_path, size, work, out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    report = {"html": str(html_path), "size": list(size), "scale_2x": "device scale factor 2 on the same viewport",
              "files": sizes, **checks, "stable": True, "errors": [], "spend": "free"}
    write(out / "render.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    r = sub.add_parser("render")
    r.add_argument("--html", type=Path, required=True)
    r.add_argument("--labels", type=Path, required=True)
    r.add_argument("--size", required=True)
    r.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run_render(args)
    except (ValueError, OSError, subprocess.SubprocessError, KeyError) as error:
        parser.exit(1, f"diagram: {error}\n")
    files = " ".join(f"{name}={w}x{h}" for name, (w, h) in report["files"].items())
    print(f"RESULT: {files} labels_ok={report['labels']}/{report['labels']} self_contained=true stable=true errors=0 spend=free out={args.out}")


if __name__ == "__main__":
    main()
