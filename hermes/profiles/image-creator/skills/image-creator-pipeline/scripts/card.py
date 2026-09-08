#!/usr/bin/env python3
"""Local card composition, fitting and measurements. No generation or network API."""

import argparse
import base64
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "create/card/references"
TEXT = {"title", "subtitle", "brand", "label", "meta", "slug", "note"}
TILING = {"destination", "tiles", "tile", "gap"}
CREATE = TEXT | TILING | {"style", "style_css", "background", "motif", "palette", "font", "tile_titles"}
EDIT = TILING | {"source", "fit", "focus", "protected", "text_band", "title", "font", "slug", "note"}
ANALYZE = TILING | {"files", "input_kind", "expected_text", "note"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, name, empty=False):
    require(isinstance(value, str) and len(value) <= 8000, f"{name}: string <=8000 characters required")
    require(empty or value.strip(), f"{name}: empty")
    require(not any(ord(c) < 32 and c not in "\n\t" for c in value), f"{name}: control character")
    return value


def integer(value, low, high, name):
    require(type(value) is int and low <= value <= high, f"{name}: integer {low}..{high} required")
    return value


def local(value):
    text(value, "path")
    path = Path(value).expanduser()
    require(path.is_absolute() and path.is_file(), "absolute existing local file required (no URLs)")
    return path.resolve()


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(local(str(path)).read_text(), object_pairs_hook=pairs)


def write(path, data):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def command(argv, **kwargs):
    proc = subprocess.run([str(v) for v in argv], capture_output=True, timeout=90, **kwargs)
    require(proc.returncode == 0, f"{argv[0]} failed: {proc.stderr.decode(errors='replace')[:1500]}")
    return proc.stdout


def destination(spec):
    name = text(spec.get("destination"), "destination")
    if re.fullmatch(r"[1-9][0-9]{1,3}x[1-9][0-9]{1,3}", name):
        w, h = map(int, name.split("x"))
        ref = {"width": w, "height": h, "status": "custom-authoring"}
    else:
        require(re.fullmatch(r"[a-z]+(?:-[a-z]+)*", name), "invalid destination")
        path = REFERENCES / "destination" / (name + ".md")
        require(path.is_file(), "unknown destination")
        # Deliberately small scalar front matter, no duplicated platform table.
        front = path.read_text().split("---", 2)[1]
        ref = {}
        for line in front.strip().splitlines():
            key, value = line.split(":", 1)
            value = value.strip()
            ref[key] = int(value) if value.isdigit() else value
    n = integer(spec.get("tiles", ref.get("tiles", 1)), 1, 4, "tiles")
    tile = spec.get("tile", ref.get("tile"))
    if name == "x-pair":
        require(n == ref["tiles"] and tile == ref["tile"], "x-pair requires tiles=2, tile=candidate (unverified)")
    elif name == "x-carousel":
        require(ref["tiles"] <= n <= ref["max_tiles"] and tile in ref["tile_options"].split("|"), "x-carousel requires tiles=3|4, tile=" + ref["tile_options"])
    else:
        require(n == 1 and "tile" not in spec and "gap" not in spec, "tile/gap controls require a tiled destination")
    w, h = ref["width"], ref["height"]
    if tile != ref.get("tile"):
        w, h = ref[f"{tile}_width"], ref[f"{tile}_height"]
    integer(w, 64, 4096, "width")
    integer(h, 64, 4096, "height")
    require(w * n * h <= 24_000_000 and w * n <= 8192, "canvas exceeds local renderer bounds")
    gap = integer(spec.get("gap", 16 if n > 1 else 0), 0, 128, "simulation gap")
    dims = {"destination": name, "width": w, "height": h, "tiles": n, "tile": tile,
            "master_width": w * n, "gap": gap, "status": ref["status"],
            "preview_kind": "local simulation, not platform evidence"}
    if "display_width_css_px" in ref:
        dims["display_width_css_px"] = integer(ref["display_width_css_px"], 64, 1080, "display width")
        dims["display_gap_css_px"] = integer(ref["display_gap_css_px"], 0, 128, "display gap")
    return dims


def titles(value, count):
    if value is None:
        return {}
    if isinstance(value, str):
        rows = []
        for line in value.splitlines():
            match = re.fullmatch(r"([1-4]): (.+)", line)
            require(match, "tile_titles lines must be 'n: text'")
            rows.append({"tile": int(match[1]), "text": match[2]})
    else:
        rows = value
    require(isinstance(rows, list), "tile_titles: list of {tile: integer, text: string} required")
    result = {}
    for row in rows:
        require(isinstance(row, dict) and set(row) == {"tile", "text"}, "invalid tile title row")
        n = integer(row["tile"], 1, count, "tile title index")
        require(n not in result, "duplicate tile title")
        result[n] = text(row["text"], "tile title")
    return result


def css_style(spec):
    style = text(spec.get("style"), "style")
    path = REFERENCES / "styles" / (style + ".md") if re.fullmatch(r"[a-z0-9-]+", style) else None
    if path and path.is_file():
        require("style_css" not in spec, "named style conflicts with style_css")
        blocks = re.findall(r"```css\n(.*?)\n```", path.read_text(), re.S)
        require(len(blocks) == 1, "style must contain exactly one canonical CSS block")
        css = blocks[0]
    else:
        require("style_css" in spec, "described style needs concrete task-local style_css; no named-style fallback")
        css = local(spec["style_css"]).read_text()
    require(len(css) <= 16000 and not re.search(r"[<>@\\]|/\*|url\s*\(|image-set\s*\(|expression\s*\(", css, re.I), "CSS forbids URLs, imports, escapes, comments and markup")
    selectors = {":root", ".stage", ".panel", ".accent", ".orb", "h1", ".label", ".brand"}
    props = {"background", "background-color", "background-size", "color", "border", "border-radius", "outline", "outline-offset", "box-shadow", "backdrop-filter", "font-weight", "letter-spacing", "--surface", "--ink", "--accent"}
    cursor = 0
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        require(not css[cursor:match.start()].strip(), "invalid CSS structure")
        require(match[1].strip() in selectors, "unsupported CSS selector")
        for declaration in match[2].split(";"):
            if not declaration.strip():
                continue
            require(":" in declaration, "invalid CSS declaration")
            prop, value = declaration.split(":", 1)
            require(prop.strip() in props and value.strip() and "!" not in value, "unsupported CSS property/value")
            if prop.strip().startswith("--"):
                require(re.fullmatch(r"#[0-9a-fA-F]{6}", value.strip()), "palette variables require #rrggbb")
        cursor = match.end()
    require(cursor and not css[cursor:].strip(), "invalid CSS")
    for role in ("surface", "ink", "accent"):
        require(re.search(r"--" + role + r"\s*:\s*#[0-9a-fA-F]{6}\s*[;}]", css), "style must declare surface/ink/accent colours")
    palette = spec.get("palette")
    if palette is not None:
        require(isinstance(palette, str) and re.fullmatch(r"#[0-9a-fA-F]{6},#[0-9a-fA-F]{6},#[0-9a-fA-F]{6}", palette), "palette: surface,ink,accent as three #rrggbb values")
        css += ":root{" + ";".join(f"--{k}:{v}" for k, v in zip(("surface", "ink", "accent"), palette.split(","))) + "}"
    return css


def validate(spec, mode):
    require(isinstance(spec, dict), "spec must be a JSON object")
    allowed = {"create": CREATE, "edit": EDIT, "analyze": ANALYZE}[mode]
    require(set(spec) <= allowed, "unknown/conflicting fields: " + ", ".join(sorted(set(spec) - allowed)))
    for name in TEXT & set(spec):
        text(spec[name], name, empty=name != "title")
    if "slug" in spec:
        require(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", spec["slug"]), "slug: lowercase words joined by hyphens")
    dims = destination(spec)
    if mode == "create":
        text(spec.get("title"), "title")
        css_style(spec)
        require(dims["tiles"] > 1 or "tile_titles" not in spec, "tile_titles requires tiled destination")
        titles(spec.get("tile_titles"), dims["tiles"])
    return dims


def raster(path):
    data = local(str(path)).read_bytes()
    require(len(data) <= 64_000_000, "asset exceeds 64MB")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise ValueError("only PNG/JPEG/WebP raster assets accepted; rasterize trusted SVG explicitly first")
    return data, mime


def image_info(path):
    data, _ = raster(path)
    with tempfile.TemporaryDirectory(prefix="card-probe-") as temp:
        safe = Path(temp) / "input"
        safe.write_bytes(data)
        result = command(["magick", "identify", "-format", "%w %h %n\n", safe]).decode().strip().splitlines()
        require(len(result) == 1, "animated/multiple-frame input unsupported")
        w, h, frames = map(int, result[0].split())
        require(frames == 1 and w * h <= 40_000_000, "asset frame/pixel bound exceeded")
        command(["magick", safe, "null:"])
    return {"width": w, "height": h, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def data_uri(path):
    image_info(path)
    data, mime = raster(path)
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def page(spec, dims, band=0):
    css = css_style(spec)
    font = local(spec["font"]) if spec.get("font") else Path("/System/Library/Fonts/\u30d2\u30e9\u30ae\u30ce\u89d2\u30b4\u30b7\u30c3\u30af W6.ttc")
    require(font.is_file(), "default Japanese font unavailable; supply an absolute font path")
    font_bytes = font.read_bytes()
    require(font.suffix.lower() in (".ttf", ".otf", ".ttc", ".woff", ".woff2") and len(font_bytes) <= 32_000_000, "unsupported font")
    encoded = base64.b64encode(font_bytes).decode()
    w, h, n = dims["width"], dims["height"], dims["tiles"]
    inset = max(16, round(min(w, h) * .1))
    size = max(24, round(min(w, h) * .105))
    minor = max(16, round(size * .38))
    parts = []
    tile_titles = titles(spec.get("tile_titles"), n)
    for index in range(1, n + 1):
        fields = {key: spec.get(key, "") if index == 1 else "" for key in TEXT}
        heading = fields["title"] if index == 1 else tile_titles.get(index, "")
        subheading = tile_titles.get(1, "") if index == 1 else ""
        esc = lambda v: html.escape(v, quote=True)
        motif = f'<img class="motif" src="{data_uri(spec["motif"])}" alt="">' if spec.get("motif") and index == 1 else ""
        parts.append(f'<section class="tile" style="left:{(index-1)*w}px"><div class="panel"></div><div class="copy">'
                     f'<div class="top"><div class="label" data-copy>{esc(fields["label"])}</div><div class="accent"></div>'
                     f'<h1 data-copy>{esc(heading)}</h1><h2 data-copy>{esc(subheading)}</h2>'
                     f'<p data-copy>{esc(fields["subtitle"])}</p>{motif}</div>'
                     f'<footer><div class="brand" data-copy>{esc(fields["brand"])}</div><div data-copy>{esc(fields["meta"])}</div></footer>'
                     '</div></section>')
    bg = f'<img class="background" src="{data_uri(spec["background"])}" alt="">' if spec.get("background") else ""
    if band:
        css += f'.panel{{display:none}}.copy{{top:auto;bottom:0;left:0;right:0;height:{band}px;padding:{minor}px;background:#f6f4ee;color:#17202e}}.accent,footer{{display:none}}.top{{margin:0}}'
    return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; font-src data:; style-src 'unsafe-inline'; script-src 'none'; connect-src 'none'; base-uri 'none'">
<title>{html.escape(spec['title'])}</title><style>
@font-face{{font-family:CardFont;src:url(data:font/ttf;base64,{encoded});font-weight:100 900}}
*{{box-sizing:border-box}}html,body{{margin:0;width:{w*n}px;height:{h}px;overflow:hidden}}
body{{font-family:CardFont,sans-serif;color:var(--ink);-webkit-font-smoothing:antialiased}}
.stage{{position:relative;width:100%;height:100%;background:var(--surface)}}
.background{{position:absolute;width:100%;height:100%;object-fit:cover}}
.orb{{position:absolute;inset:-20%;pointer-events:none}}
.tile{{position:absolute;top:0;width:{w}px;height:{h}px}}
.panel{{position:absolute;inset:{inset//2}px}}
.copy{{position:absolute;inset:{inset}px;display:flex;flex-direction:column;justify-content:space-between;gap:{minor}px}}
.top{{margin-block:auto;min-height:0}}[data-copy]{{white-space:pre-wrap;overflow-wrap:anywhere}}
h1{{font-size:{size}px;line-height:1.22;margin:0;font-weight:700}}h2{{font-size:{size*.55}px;line-height:1.3;margin:{minor}px 0 0}}
p{{font-size:{size*.45}px;line-height:1.5;margin:{minor}px 0 0}}[data-copy]:empty{{display:none}}
.label,footer{{font-size:{minor}px;line-height:1.4}}.label{{margin-bottom:{minor}px}}
.accent{{width:{size}px;height:6px;margin-bottom:{minor}px}}footer{{display:flex;justify-content:space-between;gap:{minor}px}}
footer>*{{max-width:60%}}.brand{{font-weight:600}}
.motif{{display:block;object-fit:contain;width:100%;height:{min(h*.24,w*.3):.0f}px;margin-top:{minor}px}}
{css}</style></head><body><main class="stage">{bg}<div class="orb"></div>{''.join(parts)}</main></body></html>'''


# Evaluated through stdin after fonts/assets settle, never interpolated from the spec.
LAYOUT = """(async () => {
 await document.fonts.ready;
 await Promise.all(Array.from(document.images, i => i.decode()));
 if (!document.fonts.check('32px CardFont')) throw Error('font unavailable');
 await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
 const checks=[];
 for (const tile of document.querySelectorAll('.tile')) {
   const box=tile.querySelector('.copy'), title=tile.querySelector('h1');
   const fits=()=>box.scrollHeight<=box.clientHeight+1 && box.scrollWidth<=box.clientWidth+1;
   const start=parseFloat(getComputedStyle(title).fontSize), minimum=Math.max(18,start*.6);
   let size=start;
   while (!fits() && size>minimum) { size=Math.max(minimum,size-2); title.style.fontSize=size+'px'; }
   const b=box.getBoundingClientRect(), t=tile.getBoundingClientRect();
   for (const e of tile.querySelectorAll('[data-copy]')) {
     if (!e.textContent) continue;
     const r=e.getBoundingClientRect();
     const range=document.createRange();range.selectNodeContents(e);
     const ink=range.getBoundingClientRect();
     const ok=fits() && r.left>=t.left && r.right<=t.right && r.top>=b.top-1 && r.bottom<=b.bottom+1
       && e.scrollWidth<=e.clientWidth+1 && ink.left>=t.left && ink.right<=t.right
       && ink.top>=b.top-1 && ink.bottom<=b.bottom+1;
     checks.push({text:e.textContent,ok,x:r.x,y:r.y,width:r.width,height:r.height,font:getComputedStyle(e).fontSize});
   }
 }
 return {font:document.fonts.check('32px CardFont'),checks,ok:checks.length>0 && checks.every(c=>c.ok)};
})()"""


def snapshot(document, out, dims):
    session = "card-" + uuid.uuid4().hex[:16]
    with tempfile.TemporaryDirectory(prefix="card-browser-") as temp:
        run = Path(temp)
        write(run / "browser.json", {"headed": False, "restoreSave": "never"})
        argv = ["agent-browser", "--config", str(run / "browser.json"), "--namespace", session, "--session", session, "--json"]
        env = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR", "LANG") if k in os.environ}
        env.update({"DO_NOT_TRACK": "1", "AGENT_BROWSER_IDLE_TIMEOUT_MS": "20000"})

        def call(*args, script=None):
            raw = command(argv + list(args), cwd=run, env=env, input=script.encode() if script else None)
            data = json.loads(raw)
            require(data.get("success") is True, "browser rejected command: " + str(data))
            return data.get("data", {})

        try:
            call("open", "about:blank")
            call("set", "offline", "on")
            call("set", "viewport", str(dims["master_width"]), str(dims["height"]), "1")
            call("open", document.as_uri())
            layout = call("eval", "--stdin", script=LAYOUT)["result"]
            write(out / "layout.json", layout)
            require(layout["ok"], "text overflow or font failure; inspect layout.json, revise copy/layout, never deliver clipped text")
            call("screenshot", str(out / "snapshot-a.png"))
            call("eval", "--stdin", script="new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(true))))")
            call("screenshot", str(out / "snapshot-b.png"))
            errors = call("errors")
            write(out / "browser-errors.json", errors)
            require(not errors.get("errors"), "browser page errors")
        finally:
            call("close")
    a, b = (command(["magick", out / name, "-depth", "8", "rgba:-"]) for name in ("snapshot-a.png", "snapshot-b.png"))
    require(a == b, "unstable snapshots; no final master published")
    command(["magick", out / "snapshot-a.png", "-strip", out / "master.png"])
    return layout


def finish(out, dims):
    info = image_info(out / "master.png")
    require((info["width"], info["height"]) == (dims["master_width"], dims["height"]), "wrong rendered dimensions")
    files = []
    for index in range(dims["tiles"]):
        name = f"tile-{index+1:02}.png"
        command(["magick", out / "master.png", "-crop", f"{dims['width']}x{dims['height']}+{index*dims['width']}+0", "+repage", "-strip", out / name])
        preview_width = 168 if dims["destination"] == "youtube-thumb" else 360
        command(["magick", out / name, "-resize", f"{preview_width}x", out / f"tile-{index+1:02}-preview.png"])
        files.append(name)
    combined = command(["magick", *[out / f for f in files], "+append", "-depth", "8", "rgba:-"])
    original = command(["magick", out / "master.png", "-depth", "8", "rgba:-"])
    require(combined == original, "tile reassembly differs from master pixels")
    if dims["tiles"] > 1:
        args = ["magick", "-size", f"{dims['master_width']+(dims['tiles']-1)*dims['gap']}x{dims['height']}", "xc:#777777"]
        for i, name in enumerate(files):
            args += [str(out / name), "-geometry", f"+{i*(dims['width']+dims['gap'])}+0", "-composite"]
        command(args + ["-strip", out / "simulated-gap.png"])
    if "display_width_css_px" in dims:
        width, gap = dims["display_width_css_px"], dims["display_gap_css_px"]
        height = round(dims["height"] * width / dims["width"])
        args = ["magick", "-size", f"{width*dims['tiles']+gap*(dims['tiles']-1)}x{height}", "xc:#777777"]
        for i, name in enumerate(files):
            args += ["(", str(out / name), "-resize", f"{width}x{height}!", ")",
                     "-geometry", f"+{i*(width+gap)}+0", "-composite"]
        command(args + ["-strip", out / "simulated-display.png"])
        write(out / "simulated-display.json", {
            "kind": dims["preview_kind"], "file": "simulated-display.png",
            "image_width_css_px": width, "image_height_css_px": height,
            "effective_image_gap_css_px": gap, "raster_pixels_per_css_px": 1,
            "label": f"LOCAL SIMULATION: each image {width} CSS px wide; image gap {gap} CSS px; 1 raster px = 1 CSS px. Not X UI.",
        })
    command(["magick", out / "master.png", "-resize", "360x", out / "preview.png"])
    return {"dimensions": dims, "master": info, "ordered_tiles": files, "reassembly_rgba_equal": True,
            "spend": "free", "visual_verdict": "unverified; bounded human/agent image review required"}


def create(spec, out):
    dims = validate(spec, "create")
    document = page(spec, dims)
    out.mkdir(parents=False, exist_ok=False)
    write(out / "spec.json", spec)
    write(out / "card.html", document)
    snapshot(out / "card.html", out, dims)
    report = finish(out, dims)
    write(out / "manifest.json", report)
    return report


def edit(spec, out):
    dims = validate(spec, "edit")
    source = local(spec.get("source"))
    info = image_info(source)
    fit = spec.get("fit")
    require(fit in ("cover", "contain", "pad", "focus"), "explicit fit cover|contain|pad|focus required")
    require(("focus" in spec) == (fit == "focus"), "focus coordinates required only for fit=focus")
    focus = spec.get("focus", [0.5, 0.5])
    require(isinstance(focus, list) and len(focus) == 2 and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in focus), "focus: normalized [x,y] required")
    band = integer(spec.get("text_band", 0), 0, dims["height"] // 2, "text_band")
    require(bool(spec.get("title")) == bool(band), "title and positive text_band must be provided together")
    require(not band or dims["tiles"] == 1, "text band is single-card only; rerender own tiled source spec for lettering")
    require("font" not in spec or band, "font needs text_band")
    w, h = dims["master_width"], dims["height"] - band
    sw, sh = info["width"], info["height"]
    scale = max(w / sw, h / sh) if fit in ("cover", "focus") else min(w / sw, h / sh)
    if fit == "pad":
        require(sw <= w and sh <= h, "pad never scales; source must fit")
        scale = 1
    rw, rh = math.ceil(sw * scale), math.ceil(sh * scale)
    x = max(0, min(rw - w, round(focus[0] * rw - w / 2)))
    y = max(0, min(rh - h, round(focus[1] * rh - h / 2)))
    protected = spec.get("protected", [])
    require(isinstance(protected, list), "protected: list of source-pixel [x,y,w,h] rectangles")
    for rect in protected:
        require(isinstance(rect, list) and len(rect) == 4 and all(type(v) is int and v >= 0 for v in rect), "invalid protected rectangle")
        px, py, pw, ph = rect
        require(pw > 0 and ph > 0 and px + pw <= sw and py + ph <= sh, "protected rectangle outside source")
        require(px * rw / sw >= x and py * rh / sh >= y and (px + pw) * rw / sw <= x + w and (py + ph) * rh / sh <= y + h, "destructive crop of protected content; use contain/pad or revise focus")
    out.mkdir(parents=False, exist_ok=False)
    write(out / "spec.json", spec)
    # Copy bytes to a controlled name: ImageMagick never interprets a spec path as syntax.
    (out / "source-image").write_bytes(source.read_bytes())
    args = ["magick", out / "source-image", "-resize", f"{rw}x{rh}!", "-crop", f"{min(w,rw)}x{min(h,rh)}+{x}+{y}", "+repage", "-background", "#f6f4ee", "-gravity", "center", "-extent", f"{w}x{h}"]
    command(args + ["-gravity", "north", "-extent", f"{w}x{dims['height']}", "-strip", out / ("fitted.png" if band else "master.png")])
    if band:
        render = {"title": spec["title"], "style": "flat-minimal", "background": str(out / "fitted.png")}
        if "font" in spec:
            render["font"] = spec["font"]
        write(out / "card.html", page(render, dims, band=band))
        snapshot(out / "card.html", out, dims)
    report = finish(out, dims)
    report.update({"source": info, "fit": fit, "crop_scaled_xy": [x, y], "protected_rectangles": len(protected),
                   "protected_semantics": "unverified; rectangles do not identify faces/text automatically"})
    write(out / "manifest.json", report)
    return report


def analyze(spec):
    dims = validate(spec, "analyze")
    files = spec.get("files")
    kind = spec.get("input_kind")
    require(kind in ("single", "tiles", "panorama"), "input_kind: single|tiles|panorama required")
    require(isinstance(files, list) and 1 <= len(files) <= 4, "files: ordered array of 1..4 absolute paths")
    require(len(files) == (dims["tiles"] if kind == "tiles" else 1), "input count conflicts with destination/input_kind")
    require(kind != "single" or dims["tiles"] == 1, "tiled destination needs panorama or ordered tiles")
    if "expected_text" in spec:
        text(spec["expected_text"], "expected_text")
    rows = []
    for file in files:
        info = image_info(local(file))
        expected = [dims["master_width"] if kind == "panorama" else dims["width"], dims["height"]]
        rows.append({"file": file, **info, "expected": expected, "dimensions_match": [info["width"], info["height"]] == expected})
    return {"dimensions": dims, "input_kind": kind, "ordered_measurements": rows, "spend": "free",
            "visual_checks": {"text": "unverified", "contrast": "unverified", "seams": "unverified", "platform_crop": "unverified"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("create", "edit", "analyze"))
    parser.add_argument("spec", type=Path, help="absolute JSON file; copy never travels in argv")
    parser.add_argument("--out", type=Path, help="exclusive new bundle directory (create/edit)")
    args = parser.parse_args()
    try:
        spec = load(args.spec)
        if args.mode == "analyze":
            require(args.out is None, "analyze returns measurements only; no media output")
            report = analyze(spec)
        else:
            require(args.out is not None and args.out.is_absolute() and args.out.parent.is_dir(), "absolute --out with existing parent required")
            require(not args.out.exists() and not args.out.is_symlink(), "output already exists; choose a fresh directory")
            report = {"create": create, "edit": edit}[args.mode](spec, args.out)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except (ValueError, OSError, subprocess.SubprocessError, KeyError) as error:
        parser.exit(1, f"card: {error}\n")


if __name__ == "__main__":
    main()
