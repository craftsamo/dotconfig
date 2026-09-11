#!/usr/bin/env python3
"""Local card composition, fitting and measurements. No generation or network API."""

import argparse
import base64
import hashlib
import html
from html.parser import HTMLParser
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
CREATE = TEXT | TILING | {"style", "style_css", "layout_html", "copy_blocks", "background", "motif", "palette", "font", "tile_titles"}
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
        require(dims["tiles"] > 1 or "tile_titles" not in spec, "tile_titles requires tiled destination")
        titles(spec.get("tile_titles"), dims["tiles"])
        if "layout_html" in spec:
            text(spec.get("style"), "style")
            require(not {"style_css", "palette"} & set(spec), "layout_html owns CSS; style_css/palette conflict")
            authored_fragment(spec, dims, local(spec["layout_html"]).read_bytes())
        else:
            require("copy_blocks" not in spec, "copy_blocks requires layout_html")
            css_style(spec)
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


def image_info(path, *, data=None):
    if data is None:
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
    data, mime = raster(path)
    image_info(path, data=data)
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def authored_fragment(spec, dims, source):
    """Bind task-authored static markup to exact copy/assets, not a layout preset."""
    require(len(source) <= 256_000, "layout_html exceeds 256KB")
    source = source.decode("utf-8")
    expected = {key: (1, spec[key]) for key in ("title", "subtitle", "brand", "label", "meta") if spec.get(key)}
    expected.update({f"tile-title-{n}": (n, value) for n, value in titles(spec.get("tile_titles"), dims["tiles"]).items()})
    blocks = spec.get("copy_blocks", [])
    require(isinstance(blocks, list) and len(blocks) <= 128, "copy_blocks: at most 128 {id,tile,text} blocks")
    for block in blocks:
        require(isinstance(block, dict) and set(block) == {"id", "tile", "text"}, "copy_blocks needs id, tile and exact text")
        key = text(block["id"], "copy block id")
        require(re.fullmatch(r"[a-z][a-z0-9-]{0,63}", key) and key not in expected and key not in TEXT and not key.startswith("tile-title-"), "duplicate or reserved copy block id")
        expected[key] = (integer(block["tile"], 1, dims["tiles"], "copy block tile"), text(block["text"], "copy block text"))
    require(sum(len(value) for _, value in expected.values()) <= 64_000, "authored copy exceeds 64000 characters")
    assets = {}

    def css(value):
        # Layout properties are free; resources come only from bound local inputs.
        require(not re.search(r"[<>\\]|/\*|url\s*\(|image-set\s*\(|expression\s*\(|@(?:import|font-face)\b", value, re.I),
                "authored CSS forbids resources, escapes, comments, imports and markup")
        return value

    class Fragment(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack, self.parts, self.tiles, self.copies, self.assets = [], [], [], {}, set()
            self.tile, self.copy = None, None

        def handle_starttag(self, tag, attrs):
            require(tag in {"div", "section", "main", "header", "footer", "article", "aside", "p", "span",
                            "h1", "h2", "h3", "h4", "h5", "h6", "strong", "em", "b", "i", "small",
                            "ul", "ol", "li", "figure", "figcaption", "br", "img", "style"}, "unsupported authored HTML tag: " + tag)
            inline = {"span", "strong", "em", "b", "i", "small", "br", "img"}
            require(not any(open_tag == "p" for open_tag, _, _ in self.stack) or tag in inline,
                    "p cannot contain block content; browser would repair the authored tree")
            if tag == "li":
                for open_tag, _, _ in reversed(self.stack):
                    if open_tag in {"ul", "ol"}:
                        break
                    require(open_tag != "li", "li must not implicitly close an authored li")
            require(not (tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self.stack and self.stack[-1][0] in {"h1", "h2", "h3", "h4", "h5", "h6"}),
                    "heading must not implicitly close an authored heading")
            require(len(dict(attrs)) == len(attrs), "duplicate authored HTML attribute")
            attrs = dict(attrs)
            require(set(attrs) <= {"class", "id", "style", "lang", "dir", "title", "data-card-tile", "data-card-copy", "data-card-asset"},
                    "unsupported authored HTML attribute")
            require(all(value is not None for value in attrs.values()), "authored attributes need values")
            if "style" in attrs:
                css(attrs["style"])
            if tag == "style":
                require(not self.stack and not attrs, "style must be outside tiles without attributes")
            elif "data-card-tile" in attrs:
                require(tag == "section" and not self.stack and attrs["data-card-tile"] in {str(n) for n in range(1, dims["tiles"] + 1)},
                        "data-card-tile needs one top-level section per destination tile")
                self.tile = int(attrs["data-card-tile"])
                require(self.tile not in self.tiles, "duplicate authored tile")
                self.tiles.append(self.tile)
            else:
                require(self.tile is not None, "authored content needs a tile section")
            if "data-card-copy" in attrs:
                key = attrs["data-card-copy"]
                require(tag not in {"style", "img", "br", "section"} and self.copy is None and key in expected and key not in self.copies,
                        "unknown, duplicate, empty or nested copy binding")
                require(expected[key][0] == self.tile, "copy binding belongs to a different tile; use explicit copy_blocks for additional per-tile copy")
                self.copy = key
                self.copies[key] = ""
                attrs["data-card-expected"] = expected[key][1]
            if tag == "br":
                require(self.copy is not None, "br needs a copy binding")
                self.copies[self.copy] += "\n"
            if tag == "img":
                key = attrs.get("data-card-asset")
                require(self.copy is None and key in {"background", "motif"} and spec.get(key), "img needs a supplied data-card-asset")
                if key not in assets:
                    assets[key] = data_uri(spec[key])
                attrs["src"] = assets[key]
                attrs["alt"] = ""
                self.assets.add(key)
            else:
                require("data-card-asset" not in attrs, "data-card-asset needs img")
            self.parts.append("<" + tag + "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in attrs.items()) + ">")
            if tag not in {"br", "img"}:
                self.stack.append((tag, attrs.get("data-card-copy"), "data-card-tile" in attrs))

        def handle_endtag(self, tag):
            require(self.stack and self.stack[-1][0] == tag, "unbalanced authored HTML")
            _, key, tile = self.stack.pop()
            if key is not None:
                require(self.copies[key] == expected[key][1], "authored copy differs from spec: " + key)
                self.copy = None
            if tile:
                self.tile = None
            self.parts.append("</" + tag + ">")

        def handle_startendtag(self, tag, attrs):
            require(tag in {"br", "img"}, "only void authored tags may self-close")
            self.handle_starttag(tag, attrs)

        def handle_data(self, value):
            if self.stack and self.stack[-1][0] == "style":
                self.parts.append(css(value))
            else:
                require(self.copy is not None or not value.strip(), "unbound authored text")
                if self.copy is not None:
                    self.copies[self.copy] += value
                self.parts.append(html.escape(value, quote=False))

        def handle_decl(self, value):
            raise ValueError("layout_html is a fragment, not a document")

        def unknown_decl(self, value):
            raise ValueError("unsupported authored declaration")

        def handle_pi(self, value):
            raise ValueError("unsupported authored processing instruction")

    parser = Fragment()
    parser.feed(source)
    parser.close()
    require(not parser.stack, "unclosed authored HTML")
    require(parser.tiles == list(range(1, dims["tiles"] + 1)), "authored tiles must match destination order/count")
    require(set(parser.copies) == set(expected), "missing authored copy bindings")
    require(parser.assets == {key for key in ("background", "motif") if spec.get(key)}, "unused supplied authored asset")
    return "".join(parser.parts)


def page(spec, dims, band=0, layout_source=None):
    authored = "layout_html" in spec
    css = "" if authored else css_style(spec)
    font = local(spec["font"]) if spec.get("font") else Path("/System/Library/Fonts/\u30d2\u30e9\u30ae\u30ce\u89d2\u30b4\u30b7\u30c3\u30af W6.ttc")
    require(font.is_file(), "default Japanese font unavailable; supply an absolute font path")
    font_bytes = font.read_bytes()
    require(font.suffix.lower() in (".ttf", ".otf", ".ttc", ".woff", ".woff2") and len(font_bytes) <= 32_000_000, "unsupported font")
    encoded = base64.b64encode(font_bytes).decode()
    w, h, n = dims["width"], dims["height"], dims["tiles"]
    if authored:
        require(not band, "authored layout cannot use raster text_band")
        fragment = authored_fragment(spec, dims, local(spec["layout_html"]).read_bytes() if layout_source is None else layout_source)
        return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; font-src data:; style-src 'unsafe-inline'; script-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>{html.escape(spec['title'])}</title><style>
@font-face{{font-family:CardFont;src:url(data:font/ttf;base64,{encoded});font-weight:100 900}}
*{{box-sizing:border-box}}html,body{{margin:0;width:{w*n}px;height:{h}px;overflow:hidden}}
body{{font-family:CardFont,sans-serif}}[data-card-stage]{{position:relative;width:{w*n}px;height:{h}px}}
[data-card-tile]{{position:absolute;top:0;width:{w}px;height:{h}px}}
{''.join(f'[data-card-tile="{i}"]{{left:{(i-1)*w}px}}' for i in range(1,n+1))}
[data-card-copy]{{white-space:pre-wrap}}
li{{list-style:none}}
</style></head><body><main data-card-stage data-card-authored data-card-preview-width="{168 if dims['destination'] == 'youtube-thumb' else 360}">{fragment}</main></body></html>'''
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


# This path measures authored elements without imposing template geometry or shrinking copy.
AUTHORED_LAYOUT = r"""(async () => {
 await document.fonts.ready;
 await Promise.all(Array.from(document.images, i => i.decode()));
 await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
 const stage=document.querySelector('[data-card-stage]'), checks=[], findings=[];
 const stageBox=stage.getBoundingClientRect();
 const tiles=Array.from(stage.querySelectorAll('[data-card-tile]'));
 const width=innerWidth/tiles.length, height=innerHeight;
 const contains=(a,b)=>b.left>=a.left-.5 && b.right<=a.right+.5 && b.top>=a.top-.5 && b.bottom<=a.bottom+.5;
 const visible=e=>{
   for(let p=e;p;p=p.parentElement){
     const s=getComputedStyle(p);
     if(s.display==='none'||s.visibility!=='visible'||Number(s.opacity)===0||s.contentVisibility==='hidden'||/opacity\(0(?:%|\.0+)?\)/.test(s.filter)) return false;
   }
   return true;
 };
 if(!document.fonts.check('32px CardFont')) findings.push('font unavailable');
 if(Math.abs(stageBox.left)>.5||Math.abs(stageBox.top)>.5||Math.abs(stageBox.width-innerWidth)>.5||Math.abs(stageBox.height-height)>.5) findings.push('stage geometry differs from destination');
 if(document.getAnimations().length) findings.push('animated content is not a static card');
 for(const e of [document.body,stage,...stage.querySelectorAll('*')]){
   for(const pseudo of ['::before','::after','::marker']){
     const content=getComputedStyle(e,pseudo).content;
     if(!['none','normal','""',"''"].includes(content)) findings.push('unbound generated content');
   }
   const s=getComputedStyle(e);
   if(s.display==='list-item'&&s.listStyleType!=='none') findings.push('unbound list marker');
 }
 for(let i=0;i<tiles.length;i++){
   const tile=tiles[i], t=tile.getBoundingClientRect();
   if(Math.abs(t.left-i*width)>.5||Math.abs(t.top)>.5||Math.abs(t.width-width)>.5||Math.abs(t.height-height)>.5) findings.push('tile geometry differs from destination');
   const boxes=[];
   for(const e of tile.querySelectorAll('[data-card-copy]')){
     const r=e.getBoundingClientRect(), range=document.createRange();range.selectNodeContents(e);
     const ink=range.getBoundingClientRect(), s=getComputedStyle(e);
     const rects=Array.from(range.getClientRects()).filter(b=>b.width>0&&b.height>0);
     let ok=e.innerText===e.dataset.cardExpected&&visible(e)&&r.width>0&&r.height>0&&ink.width>0&&ink.height>0&&contains(t,r)&&contains(t,ink)
       &&e.scrollWidth<=e.clientWidth+1&&e.scrollHeight<=e.clientHeight+1;
     // Inspect text-bearing descendants, not empty decorative nodes. Complex masks
     // and painted occlusion remain visual QA, not a claim of complete visibility.
     const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);
     for(let node=walker.nextNode();node;node=walker.nextNode()){
       if(!node.textContent.trim()) continue;
       const span=document.createRange();span.selectNodeContents(node);
       const glyph=span.getBoundingClientRect();
       if(!visible(node.parentElement)||glyph.width<=0||glyph.height<=0||!contains(t,glyph)) ok=false;
       for(let p=node.parentElement;p&&p!==document.body;p=p.parentElement){
         const ps=getComputedStyle(p), b=p.getBoundingClientRect();
         if(ps.overflowX!=='visible'&&(glyph.left<b.left-.5||glyph.right>b.right+.5)) ok=false;
         if(ps.overflowY!=='visible'&&(glyph.top<b.top-.5||glyph.bottom>b.bottom+.5)) ok=false;
       }
     }
     const row={id:e.dataset.cardCopy,text:e.innerText,ok,x:r.x,y:r.y,width:r.width,height:r.height,font:s.fontSize,
       display_font_px:parseFloat(s.fontSize)*Number(stage.dataset.cardPreviewWidth)/width};
     checks.push(row);boxes.push({row,rects});
   }
   for(let a=0;a<boxes.length;a++) for(let b=a+1;b<boxes.length;b++){
     if(boxes[a].rects.some(x=>boxes[b].rects.some(y=>Math.min(x.right,y.right)-Math.max(x.left,y.left)>.5&&Math.min(x.bottom,y.bottom)-Math.max(x.top,y.top)>.5))){
       boxes[a].row.ok=false;boxes[b].row.ok=false;findings.push('copy overlap');
     }
   }
 }
 return {authored:true,font:document.fonts.check('32px CardFont'),checks,findings,
   ok:checks.length>0&&checks.every(c=>c.ok)&&findings.length===0,
   visual_verdict:'unverified: contrast, complex masks, occlusion, glyph coverage and reduced-size readability need visual review'};
})()"""


def snapshot(document, out, dims, layout_script=LAYOUT):
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
            layout = call("eval", "--stdin", script=layout_script)["result"]
            write(out / "layout.json", layout)
            failures = list(layout.get("findings", []))
            failures.extend("copy check failed: " + row.get("id", row.get("text", "unknown")) for row in layout.get("checks", []) if not row.get("ok"))
            require(layout["ok"], ("authored layout rejected: " + "; ".join(failures) + "; inspect layout.json; do not change protected copy to fit"
                                  if layout.get("authored") else "text overflow or font failure; inspect layout.json, revise copy/layout, never deliver clipped text"))
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
    source = local(spec["layout_html"]).read_bytes() if "layout_html" in spec else None
    document = page(spec, dims, layout_source=source)
    out.mkdir(parents=False, exist_ok=False)
    write(out / "spec.json", spec)
    write(out / "card.html", document)
    if source is not None:
        with (out / "source-layout.html").open("xb") as stream:
            stream.write(source)
    snapshot(out / "card.html", out, dims, layout_script=AUTHORED_LAYOUT if source is not None else LAYOUT)
    report = finish(out, dims)
    if source is not None:
        report["layout_source_sha256"] = hashlib.sha256(source).hexdigest()
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
