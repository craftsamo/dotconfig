#!/usr/bin/env python3
"""Render an Assistant-authored design as an inert, versioned HTML diagram."""

import argparse
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
from urllib.parse import urlsplit


LANES = ("visual", "camera", "text", "audio")
EPSILON = 1e-6
ROOT_FIELDS = "version title goal duration timing open_items reference_note sources visual_system components scenes"
NODE_FIELDS = {"text": "content weight", "surface": "shape pattern pattern_ink"}
TEXT_WEIGHTS = {"regular": 400, "medium": 500, "bold": 700}
SHAPES = ("rect", "notch-top-right", "rounded", "pill", "circle")
PATTERNS = ("none", "vertical", "diagonal", "chevron", "horizontal", "dots")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names, where):
    require(isinstance(value, dict), f"{where}: expected object")
    expected = set(names.split())
    require(set(value) == expected,
            f"{where}: missing {sorted(expected - set(value))}; unknown {sorted(set(value) - expected)}")


def text(value):
    require(isinstance(value, str) and 0 < len(value.strip()) <= 4000, "expected nonempty text <=4000 characters")
    require(not any(ord(c) < 32 and c not in "\n\t" for c in value), "control character in text")
    return value


def number(value, low, high):
    require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
            f"expected finite number in {low}..{high}")
    return value


def items(value, low, high):
    require(isinstance(value, list) and low <= len(value) <= high, f"expected list of {low}..{high} items")
    return value


def identity(value, seen):
    require(isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", value), "invalid id")
    require(value not in seen, f"duplicate id: {value}")
    seen.add(value)


def references(value, known, minimum=0):
    items(value, minimum, len(known))
    require(all(isinstance(item, str) and item in known for item in value), "unknown reference id")
    require(len(set(value)) == len(value), "duplicate reference id")


def validate(spec):
    require(isinstance(spec, dict), "design: expected object")
    version = spec.get("version")
    fields(spec, ROOT_FIELDS + (" frame" if version == 2 else ""), "design")
    require(type(version) is int and version in (1, 2), "unsupported version")
    for key in ("title", "goal", "reference_note"):
        text(spec[key])
    duration = number(spec["duration"], 0.001, 3600)
    require(spec["timing"] in ("estimated", "agreed"), "invalid timing status")
    for issue in items(spec["open_items"], 0, 80):
        text(issue)
    source_ids = set()
    for source in items(spec["sources"], 0, 16):
        fields(source, "id url observed inspection adopt avoid", "source")
        identity(source["id"], source_ids)
        for key in ("url", "observed", "inspection", "adopt", "avoid"):
            text(source[key])
        url = urlsplit(source["url"])
        require(url.scheme == "https" and url.hostname and not url.username and not url.password,
                "source URL must be HTTPS without credentials")
    system = spec["visual_system"]
    fields(system, "typography palette geometry surfaces", "visual_system")
    for key in ("typography", "geometry", "surfaces"):
        text(system[key])
    palette = system["palette"]
    require(isinstance(palette, dict) and 2 <= len(palette) <= 16, "palette needs 2..16 colors")
    palette_ids = set()
    for name, color in palette.items():
        identity(name, palette_ids)
        require(isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color), "invalid palette color")
    if version == 2:
        frame = spec["frame"]
        fields(frame, "aspect background", "frame")
        ratio = isinstance(frame["aspect"], str) and re.fullmatch(r"([1-9][0-9]?):([1-9][0-9]?)", frame["aspect"])
        require(ratio and max(int(ratio[1]), int(ratio[2])) <= 64, "frame aspect must be W:H with integers 1..64")
        require(isinstance(frame["background"], str) and frame["background"] in palette, "unknown frame background")
    component_ids = set()
    for component in items(spec["components"], 1, 80):
        fields(component, "id name anatomy typography surface states reference_ids", "component")
        identity(component["id"], component_ids)
        for key in ("name", "anatomy", "typography", "surface", "states"):
            text(component[key])
        references(component["reference_ids"], source_ids)
    scene_ids, event_ids, used_components = set(), set(), set()
    previous_end = 0
    for scene in items(spec["scenes"], 1, 60):
        fields(scene, "id title start end purpose focus entry exit reference_ids events absent_lanes keyframes", "scene")
        identity(scene["id"], scene_ids)
        for key in ("title", "purpose", "focus", "entry", "exit"):
            text(scene[key])
        start = number(scene["start"], 0, duration)
        end = number(scene["end"], 0, duration)
        require(start < end and abs(start - previous_end) <= EPSILON, "scenes must be contiguous and ordered")
        previous_end = end
        references(scene["reference_ids"], source_ids)
        absent = scene["absent_lanes"]
        require(isinstance(absent, dict) and set(absent) <= set(LANES[1:]), "invalid absent_lanes")
        for reason in absent.values():
            text(reason)
        present, changes = set(), []
        covered, last_start = start, start
        for event in items(scene["events"], 1, 80):
            fields(event, "id lane kind start end subject before during after trigger trajectory pacing component_ids reference_ids", "event")
            identity(event["id"], event_ids)
            require(event["lane"] in LANES and event["lane"] not in absent, "invalid or absent event lane")
            present.add(event["lane"])
            require(event["kind"] in ("change", "hold"), "invalid event kind")
            a = number(event["start"], start, end)
            b = number(event["end"], start, end)
            require(a < b and a >= last_start, "events must be positive intervals ordered by start")
            last_start = a
            for key in ("subject", "before", "during", "after", "trigger", "trajectory", "pacing"):
                text(event[key])
            references(event["component_ids"], component_ids, 1)
            references(event["reference_ids"], source_ids)
            used_components.update(event["component_ids"])
            if event["lane"] == "visual":
                require(a <= covered + EPSILON, "visual timeline gap: specify a deliberate hold")
                covered = max(covered, b)
            if event["kind"] == "change":
                changes.append(event)
        require(abs(covered - end) <= EPSILON, "visual timeline does not cover scene end")
        require(present | set(absent) == set(LANES), "missing lane or absence explanation")
        times = []
        # Enough for both endpoints and an interior state of every allowed event,
        # even when all 80 intervals overlap with different boundaries.
        frames = items(scene["keyframes"], 2, 242)
        for frame in frames:
            fields(frame, "at label nodes", "keyframe")
            at = number(frame["at"], start, end)
            require(not times or at > times[-1], "keyframes must be strictly ordered")
            times.append(at)
            text(frame["label"])
            keys = set()
            for node in items(frame["nodes"], 1, 80):
                if version == 1:
                    fields(node, "component x y w h label fill", "node")
                else:
                    require(isinstance(node, dict) and node.get("kind") in NODE_FIELDS, "node kind must be text or surface")
                    fields(node, "component kind key x y w h label fill opacity " + NODE_FIELDS[node["kind"]], "node")
                    identity(node["key"], keys)
                    number(node["opacity"], 0, 1)
                    if node["kind"] == "text":
                        require(len(text(node["content"])) <= 80 and "\n" not in node["content"], "text content is one line of <=80 characters")
                        require(node["weight"] in TEXT_WEIGHTS, "invalid text weight")
                    else:
                        require(node["shape"] in SHAPES, "invalid surface shape")
                        require(node["pattern"] in PATTERNS, "invalid surface pattern")
                        require(isinstance(node["pattern_ink"], str) and node["pattern_ink"] in palette, "unknown pattern ink")
                require(isinstance(node["component"], str) and node["component"] in component_ids, "unknown node component")
                require(isinstance(node["fill"], str) and node["fill"] in palette, "unknown node color")
                text(node["label"])
                x, y = number(node["x"], -100, 200), number(node["y"], -100, 200)
                w, h = number(node["w"], 0.001, 300), number(node["h"], 0.001, 300)
                require(x + w <= 200 and y + h <= 200, "node exceeds diagram overscan")
        require(abs(times[0] - start) <= EPSILON and abs(times[-1] - end) <= EPSILON,
                "keyframes must include scene endpoints")
        for event in changes:
            require(any(event["start"] < t < event["end"] for t in times),
                    f"{event['id']}: missing intermediate keyframe")
    require(abs(previous_end - duration) <= EPSILON, "scenes must cover duration")
    require(used_components == component_ids, "unused component design")
    return spec


def esc(value):
    return html.escape(str(value), quote=True)


def details(value, keys):
    return "<dl>" + "".join(f"<dt>{esc(k.replace('_', ' '))}</dt><dd>{esc(value[k])}</dd>" for k in keys) + "</dl>"


def source_links(ids):
    return "<p>References: " + (", ".join(f'<a href="#source-{esc(i)}">{esc(i)}</a>' for i in ids) or "Original proposal / see reference note") + "</p>"


CSS = """
:root{color-scheme:light;--ink:#182330;--paper:#f4f2ed;--line:#c3c8ca;--accent:#235b72}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:clamp(16px,4vw,48px)}h1{font-size:clamp(28px,5vw,48px);line-height:1.15}
h2{margin-top:2.5rem;border-top:2px solid var(--ink);padding-top:1rem}h3,h4,p{margin:.6rem 0}
p,dd,dt,h1,h2,h3,h4,a,figcaption,li{overflow-wrap:anywhere;white-space:pre-wrap}a{color:#16516c}
.badge{font-size:12px;letter-spacing:.12em;text-transform:uppercase}.notice{border-left:4px solid var(--accent);padding:12px 16px;background:#e4edf0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:16px}
article,figure{min-width:0;margin:0;padding:16px;background:#fff;border:1px solid var(--line);border-radius:8px}
dl{margin:12px 0}dt{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#45535d}dd{margin:0 0 10px}
.ruler,.lane{height:18px;background:#dde3e4;position:relative;border-radius:3px;overflow:hidden}
.bar{position:absolute;top:0;height:100%;background:var(--accent);border-right:2px solid white}
.lane{height:10px}.lane-name{font-size:13px;margin-top:10px}.events{display:grid;gap:12px;margin-top:20px}
.time{font-variant-numeric:tabular-nums;font-weight:650}.frames{margin:20px 0}.frame{width:100%;height:auto;display:block;overflow:hidden;background:#e9ecee;border:1px solid var(--line)}
figcaption{font-size:14px}.swatch{display:inline-block;width:1.3em;height:1.3em;vertical-align:middle;border:1px solid #64727a;margin-right:8px}
.legend{padding-left:24px}.muted{color:#4c5b65;font-size:14px}@media print{article,figure{break-inside:avoid}body{background:white}}
"""


def render(spec, design_sha256):
    require(isinstance(design_sha256, str) and re.fullmatch(r"[a-f0-9]{64}", design_sha256), "invalid design identity")
    palette = spec["visual_system"]["palette"]
    parts = ["<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
             f"<title>{esc(spec['title'])}</title><style>{CSS}</style></head><body><main>",
             '<div class="badge">Visual story / planning document</div>',
             f"<h1>{esc(spec['title'])}</h1><p>{esc(spec['goal'])}</p>",
             f'<p class="muted">Design ID: sha256:{design_sha256} / schema v{spec["version"]}</p>',
             '<p class="notice">Design proposal, not a rendered preview or approval. Diagrams show spatial intent, not finished component quality or verified motion.</p>',
             f"<p class=\"time\">{spec['duration']:g}s / timing: {esc(spec['timing'])} (not measured playback)</p>"]
    if spec["open_items"]:
        parts += ['<h2>Discussion only / unresolved</h2><ul>',
                  *(f"<li>{esc(item)}</li>" for item in spec["open_items"]), "</ul>"]
    parts.append('<h2>Overview</h2><div class="ruler" aria-label="Scene durations">')
    for scene in spec["scenes"]:
        left = scene["start"] / spec["duration"] * 100
        width = (scene["end"] - scene["start"]) / spec["duration"] * 100
        parts.append(f'<a class="bar" href="#scene-{scene["id"]}" style="left:{left:.6f}%;width:{width:.6f}%" aria-label="{esc(scene["title"])}"></a>')
    parts.append('</div><ol class="legend">')
    for scene in spec["scenes"]:
        parts.append(f'<li><a href="#scene-{scene["id"]}">{esc(scene["title"])}</a> <span class="time">{scene["start"]:g}-{scene["end"]:g}s</span></li>')
    parts.append("</ol><h2>Visual system</h2>")
    parts.append(details(spec["visual_system"], ("typography", "geometry", "surfaces")))
    for name, color in palette.items():
        parts.append(f'<p><span class="swatch" style="background:{color}"></span>{esc(name)} {color}</p>')
    for scene in spec["scenes"]:
        parts.append(f'<section id="scene-{scene["id"]}"><h2>{esc(scene["title"])}</h2><p class="time">{scene["start"]:g}-{scene["end"]:g}s</p>')
        parts.append(details(scene, ("purpose", "focus", "entry", "exit")))
        parts.append(source_links(scene["reference_ids"]))
        for lane in LANES:
            parts.append(f'<div class="lane-name">{lane}</div>')
            if lane in scene["absent_lanes"]:
                parts.append(f'<p class="muted">Absent: {esc(scene["absent_lanes"][lane])}</p>')
                continue
            parts.append('<div class="lane">')
            for event in scene["events"]:
                if event["lane"] == lane:
                    length = scene["end"] - scene["start"]
                    left = (event["start"] - scene["start"]) / length * 100
                    width = (event["end"] - event["start"]) / length * 100
                    parts.append(f'<a class="bar" href="#event-{event["id"]}" style="left:{left:.6f}%;width:{width:.6f}%" aria-label="{esc(event["subject"])}"></a>')
            parts.append("</div>")
        parts.append('<div class="grid frames">')
        for index, frame in enumerate(scene["keyframes"]):
            if spec["version"] == 2:
                reference = scene["keyframes"][index - 1] if index else None
                parts.append(f'<figure>{board_svg(spec, frame, reference)}<figcaption><span class="time">{frame["at"]:g}s</span>{esc(frame["label"])}</figcaption></figure>')
                continue
            parts.append(f'<figure><svg class="frame" viewBox="0 0 400 240" role="img"><title>{esc(frame["label"])}</title>')
            for node in frame["nodes"]:
                x, y, w, h = (node[k] * factor for k, factor in (("x", 4), ("y", 2.4), ("w", 4), ("h", 2.4)))
                color = palette[node["fill"]]
                rgb = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
                ink = "#182330" if sum(c * p for c, p in zip(rgb, (.2126, .7152, .0722))) > 145 else "#ffffff"
                parts.append(f'<g><title>{esc(node["component"])}: {esc(node["label"])}</title><rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" fill="{color}" stroke="#64727a"/>')
                # The exact label remains below; tiny geometry never forces tiny type.
                parts.append(f'<text x="{x + 4:g}" y="{y + 14:g}" fill="{ink}" font-size="12">{esc(node["component"][:12])}</text></g>')
            parts.append(f'</svg><figcaption><b>{frame["at"]:g}s</b> {esc(frame["label"])}</figcaption><ul>')
            for node in frame["nodes"]:
                parts.append(f'<li>{esc(node["component"])}: {esc(node["label"])}</li>')
            parts.append("</ul></figure>")
        parts.append('</div><div class="events">')
        for event in scene["events"]:
            parts.append(f'<article id="event-{event["id"]}"><div class="badge">{event["lane"]} / {event["kind"]}</div><h3>{esc(event["subject"])}</h3><p class="time">{event["start"]:g}-{event["end"]:g}s</p>')
            parts.append(details(event, ("before", "during", "after", "trigger", "trajectory", "pacing")))
            parts.append('<p>Components: ' + ", ".join(f'<a href="#component-{i}">{i}</a>' for i in event["component_ids"]) + "</p>")
            parts.append(source_links(event["reference_ids"]) + "</article>")
        parts.append("</div></section>")
    parts.append('<h2>Component designs</h2><div class="grid">')
    for component in spec["components"]:
        parts.append(f'<article id="component-{component["id"]}"><h3>{esc(component["name"])}</h3>')
        parts.append(details(component, ("anatomy", "typography", "surface", "states")))
        parts.append(source_links(component["reference_ids"]) + "</article>")
    parts.append(f'</div><h2>Reference analysis</h2><p>{esc(spec["reference_note"])}</p>')
    for source in spec["sources"]:
        parts.append(f'<article id="source-{source["id"]}"><h3>{esc(source["id"])}</h3><a href="{esc(source["url"])}" rel="noreferrer noopener">{esc(source["url"])}</a>')
        parts.append(details(source, ("inspection", "observed", "adopt", "avoid")) + "</article>")
    parts.append('<p class="muted">Structural checks are not artistic acceptance. Sources are inspiration, not reuse or upload permission. Scene endpoints are conceptual diagram states, not encoded frame timestamps.</p></main></body></html>')
    return "\n".join(parts)


def validate_review(review, spec, design_sha256):
    """Check authored overview coverage; never infer or shorten its meaning."""
    fields(review, "version design_sha256 language title summary issues sections", "review")
    require(type(review["version"]) is int and review["version"] == 1, "unsupported review version")
    require(review["design_sha256"] == design_sha256, "review is bound to a different design")
    require(review["language"] in ("en", "ja"), "unsupported review language")
    for key, limit in (("title", 60), ("summary", 160)):
        require(len(text(review[key])) <= limit, f"review {key} exceeds {limit} characters")
    issues = items(review["issues"], len(spec["open_items"]), len(spec["open_items"]))
    for index, issue in enumerate(issues):
        fields(issue, "index summary", "review issue")
        require(type(issue["index"]) is int and issue["index"] == index, "every open item needs its own ordered summary")
        require(len(text(issue["summary"])) <= 80, "issue summary exceeds 80 characters")
    scenes = {scene["id"]: scene for scene in spec["scenes"]}
    section_ids, seen_scene_order = set(), []
    groups = {scene_id: [] for scene_id in scenes}
    for section in items(review["sections"], 1, 160):
        fields(section, "id scene title summary start end event_ids previews", "review section")
        identity(section["id"], section_ids)
        require(isinstance(section["scene"], str) and section["scene"] in scenes, "unknown review scene")
        scene = scenes[section["scene"]]
        groups[scene["id"]].append(section)
        if not seen_scene_order or seen_scene_order[-1] != scene["id"]:
            seen_scene_order.append(scene["id"])
        for key, limit in (("title", 60), ("summary", 160)):
            require(len(text(section[key])) <= limit, f"section {key} exceeds {limit} characters")
        start = number(section["start"], scene["start"], scene["end"])
        end = number(section["end"], scene["start"], scene["end"])
        require(start < end, "review section needs a positive interval")
        events = {event["id"]: event for event in scene["events"]}
        references(section["event_ids"], events, 1)
        for event_id in section["event_ids"]:
            event = events[event_id]
            require(max(start, event["start"]) < min(end, event["end"]), "review event does not intersect its section")
        frame_times = {frame["at"] for frame in scene["keyframes"]}
        previous = None
        for preview in items(section["previews"], 1, 3):
            fields(preview, "at caption", "review preview")
            at = number(preview["at"], start, end)
            require(at in frame_times, "preview must identify a supplied keyframe")
            require(previous is None or previous < at, "previews must be strictly ordered")
            previous = at
            require(len(text(preview["caption"])) <= 32, "preview caption exceeds 32 characters")
    require(seen_scene_order == list(scenes), "review must retain every scene in order")
    for scene_id, scene in scenes.items():
        cursor = scene["start"]
        for section in groups[scene_id]:
            require(section["start"] == cursor, "review section gap or overlap")
            cursor = section["end"]
        require(cursor == scene["end"], "review does not cover the scene")
        for event in scene["events"]:
            cursor, middle_visible = event["start"], False
            for section in groups[scene_id]:
                if event["id"] not in section["event_ids"]:
                    continue
                start, end = max(section["start"], event["start"]), min(section["end"], event["end"])
                require(start <= cursor, f"review omits part of event {event['id']}")
                cursor = max(cursor, end)
                middle_visible |= any(event["start"] < p["at"] < event["end"] for p in section["previews"])
            require(cursor == event["end"], f"review omits event {event['id']}")
            require(event["kind"] != "change" or middle_visible,
                    f"review hides the intermediate state of {event['id']}")
    return review


# Localized interface labels keep the authored overview separate from the full
# producer vocabulary. No translation or summary is generated by the renderer.
REVIEW_LABELS = {
    "en": {
        "issues": "Decisions needed", "issue_detail": "Full text of the open questions",
        "still": "still", "legend": "Orange on a board: dashed = where it was, arrow = movement, solid = appears, cross = leaves.",
        "visual": "Visual", "camera": "Camera", "text": "Text", "audio": "Audio", "change": "Change", "hold": "Hold",
        "before": "Before", "during": "During", "after": "After", "trigger": "Trigger", "trajectory": "Trajectory", "pacing": "Pacing",
        "scene": "Scene", "purpose": "Purpose", "focus": "Focus", "entry": "Entry", "exit": "Exit", "absent": "Absent",
        "system": "Overall look", "parts": "Parts introduced here", "anatomy": "Anatomy", "typography": "Typography", "surface": "Surface",
        "geometry": "Geometry", "surfaces": "Surfaces", "states": "States", "references": "References",
        "inspection": "Inspected evidence", "observed": "Observed", "adopt": "Adopt", "avoid": "Avoid", "unit": "s", "rail": "Timeline",
        "spec": "Full written specification: spec.html in the same bundle.",
        "move": "Moves", "resize": "Resizes", "appear": "Appears", "leave": "Leaves", "fade": "Opacity", "frames": "Frames in this event",
        "all": "All", "filter": "Lane", "log": "Events",
    },
    "ja": {
        "issues": "判断してほしいこと", "issue_detail": "判断してほしいことの全文",
        "still": "静止", "legend": "ボードの橙：破線＝元の位置、矢印＝動き、実線＝新しく現れる、×＝消える。",
        "visual": "画面", "camera": "カメラ", "text": "文字", "audio": "音", "change": "変化", "hold": "静止",
        "before": "変化前", "during": "途中の動き", "after": "変化後", "trigger": "きっかけ", "trajectory": "経路・重なり", "pacing": "速度・間",
        "scene": "場面", "purpose": "目的", "focus": "注目するもの", "entry": "開始状態", "exit": "終了状態", "absent": "使用しない要素",
        "system": "全体の見た目", "parts": "ここで初めて現れる部品", "anatomy": "形と構成", "typography": "文字・アイコン", "surface": "材質・境界",
        "geometry": "配置・余白", "surfaces": "面・光・重なり", "states": "状態", "references": "参考",
        "inspection": "確認した範囲", "observed": "観察したこと", "adopt": "取り入れること", "avoid": "取り入れないこと", "unit": "秒", "rail": "時間の流れ",
        "spec": "文章の仕様は同じ束の spec.html にあります。",
        "move": "移動", "resize": "大きさ", "appear": "出現", "leave": "消える", "fade": "濃さ", "frames": "この区間のコマ",
        "all": "すべて", "filter": "レーン", "log": "できごと",
    }
}

REVIEW_CSS = """
/* Tokens follow Notion's published system: warm neutrals, whisper borders, compressed bold headings,
   one saturated accent. Fonts are system (CSP forbids remote assets): SF/Hiragino on Apple, Yu/Noto elsewhere.
   Layout: an audit-log style list. One row per event; scene headers group rows; each row is its own disclosure. */
:root{color-scheme:light;--ink:rgba(0,0,0,.95);--ink-2:#615d59;--ink-3:#a39e98;--paper:#fff;--warm:#f6f5f4;--line:rgba(0,0,0,.1);
--accent:#0075de;--focus:#097fe8;--badge-bg:#f2f9ff;--badge:#097fe8;--mark:#ff7a1a;--gutter:20px;--thumb:72px;--frame:104px;
--shadow:rgba(0,0,0,.04) 0 4px 18px,rgba(0,0,0,.027) 0 2px 7.8px,rgba(0,0,0,.02) 0 .8px 2.9px,rgba(0,0,0,.01) 0 .2px 1px}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;overscroll-behavior-y:none}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic UI","Noto Sans JP",system-ui,sans-serif;font-feature-settings:"palt","lnum"}
.wrap{max-width:860px;margin:auto;padding-left:var(--gutter);padding-right:var(--gutter)}
p,h1,h2,li,a,summary,span,label,figcaption{overflow-wrap:anywhere}p{margin:0 0 8px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}[id]{scroll-margin-top:16px}
header{padding-top:48px;padding-bottom:20px}h1{font-size:34px;line-height:1.08;letter-spacing:-.9px;font-weight:700;margin:0 0 12px}
.lead{font-size:17px;line-height:1.45;color:var(--ink-2);max-width:36em;margin:0 0 8px}
.meta{font-size:12px;line-height:1.33;letter-spacing:.125px;color:var(--ink-3);font-variant-numeric:tabular-nums;margin:0}
.decisions{background:var(--warm);border:1px solid var(--line);border-radius:12px;padding:14px 18px 12px;margin:24px 0 0}
.label{font-size:14px;line-height:1.43;font-weight:500;color:var(--ink-2);margin:0 0 6px}
.issues{margin:0;padding:0 0 0 1.4em;font-size:16px;line-height:1.5}.issues li{margin:3px 0;padding-left:2px}
.legend{font-size:13px;line-height:1.43;color:var(--ink-2);margin:16px 0 0}.legend:before{content:"";display:inline-block;width:14px;height:0;border-top:2px dashed var(--mark);vertical-align:middle;margin-right:8px}
.chip{display:inline-block;font-size:12px;font-weight:500;letter-spacing:.125px;line-height:1.33;padding:2px 8px;border-radius:9999px;border:1px solid var(--line);color:var(--ink-2);background:var(--paper);font-variant-numeric:tabular-nums;white-space:nowrap}
.chip.change{background:#fff4ec;color:#b8480a;border-color:#ffc9a3}.chip.kind{background:var(--warm)}
/* Lane filter: radios before the list, CSS-only. Inputs stay focusable but off-canvas. */
.lane-input{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.filters{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:0 0 10px}.filters .label{margin:0 6px 0 0}
.filters label{cursor:pointer;display:inline-block;font-size:13px;font-weight:500;line-height:1.33;padding:5px 12px;border-radius:9999px;border:1px solid var(--line);color:var(--ink-2);background:var(--paper);user-select:none;min-height:30px}
.filters label:hover{border-color:var(--ink-3)}
#lane-all:checked~.wrap label[for=lane-all],#lane-visual:checked~.wrap label[for=lane-visual],#lane-camera:checked~.wrap label[for=lane-camera],#lane-text:checked~.wrap label[for=lane-text],#lane-audio:checked~.wrap label[for=lane-audio]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
#lane-visual:checked~.wrap .row:not([data-lane=visual]),#lane-camera:checked~.wrap .row:not([data-lane=camera]),#lane-text:checked~.wrap .row:not([data-lane=text]),#lane-audio:checked~.wrap .row:not([data-lane=audio]){display:none}
.lane-input:focus-visible~.wrap label[for]{outline:2px solid var(--focus);outline-offset:2px}
.log{list-style:none;margin:0;padding:0;border:1px solid var(--line);border-radius:10px;background:var(--paper);overflow:hidden}
.section{background:var(--warm);border-top:1px solid var(--line);padding:10px 16px 9px}.log>.section:first-child{border-top:0}
.section h2{font-size:15px;line-height:1.4;font-weight:600;margin:0;display:flex;justify-content:space-between;gap:12px;align-items:baseline}
.chip.time{background:var(--badge-bg);color:var(--badge);border-color:transparent;font-weight:600}.section .when{align-self:center;flex:none}
.section .copy{display:block;font-size:13px;line-height:1.45;color:var(--ink-2);margin:2px 0 0;max-width:40em}
.row{margin:0;border-top:1px solid var(--line)}.section+.row{border-top:0}
.line{display:grid;grid-template-columns:20px minmax(0,1fr) auto;column-gap:12px;padding:12px 16px;position:relative}
summary.line{cursor:pointer;list-style:none;user-select:none}summary.line::-webkit-details-marker{display:none}
summary.line:hover{background:#fafaf9}summary:focus-visible{outline:2px solid var(--focus);outline-offset:-2px}
.row:not(.last) .line:before{content:"";position:absolute;left:25.5px;top:36px;bottom:0;width:1px;background:var(--line)}
.glyph{width:20px;height:20px;border-radius:50%;border:1px solid var(--line);background:var(--paper);color:var(--ink-3);display:flex;align-items:center;justify-content:center;margin-top:1px}
.glyph svg{width:12px;height:12px;border:0;box-shadow:none;border-radius:0;display:block}
.body{min-width:0}.head{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 12px;align-items:baseline}
.title{font-size:14px;line-height:1.43;font-weight:500}.at{font-size:12px;color:var(--ink-2);font-variant-numeric:tabular-nums;white-space:nowrap}
.tags{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:6px 0 0;font-size:12px}.actor{font-weight:600;color:var(--ink);margin-right:2px}
.thumb{grid-column:3;align-self:start}.thumb svg{height:var(--thumb);width:auto;border-radius:4px}
.row.plain .line{grid-template-columns:20px minmax(0,1fr) auto}
.chip.more{background:var(--badge-bg);color:var(--badge);border-color:transparent;font-weight:600}.chip.more:before{content:"+ ";font-weight:700}
.row details[open] .chip.more:before{content:"− "}.row details[open]>summary.line{background:#fafaf9}
.frames{border-top:1px dashed var(--line);background:#fafaf9;padding:12px 16px 14px 48px}
.frames .label{margin:0 0 4px}
.strip{list-style:none;margin:0;padding:0 0 0 20px;position:relative}
.strip:before{content:"";position:absolute;left:5px;top:18px;bottom:18px;width:1px;background:var(--ink-3)}
.frame{position:relative;display:grid;grid-template-columns:var(--frame) minmax(0,1fr);gap:12px;align-items:start;padding:9px 0}
.frame:before{content:"";position:absolute;left:-19px;top:20px;width:9px;height:9px;border-radius:50%;background:var(--paper);border:1px solid var(--ink-3)}
.landscape .frame{grid-template-columns:minmax(0,1.4fr) minmax(0,1fr)}
svg{width:100%;height:auto;display:block;overflow:hidden;border:1px solid var(--line);border-radius:6px;box-shadow:var(--shadow)}
.fname{display:block;font-size:14px;line-height:1.43;font-weight:500;margin:4px 0 6px}.frame .chip.time{margin:0 0 6px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.parts{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:12px;margin:8px 0 2px}
.parts .label{grid-column:1/-1;margin:14px 0 0}.parts figure{min-width:0;margin:0}.parts figcaption{font-size:13px;font-weight:500;margin-top:6px}
#issues{margin:20px 0 0}#issues summary{cursor:pointer;min-height:44px;padding:11px 0;font-size:15px;line-height:1.33;font-weight:500;color:var(--ink-2)}#issues summary::marker{color:var(--ink-3)}
.frames-issues{padding:8px 0 4px}.frames-issues ol{margin:0;padding-left:1.4em}
.ids{margin:32px 0 0;padding:20px 0 40px;border-top:1px solid var(--line);font:12px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--ink-3);overflow-wrap:anywhere}
@media(min-width:640px){:root{--thumb:88px;--frame:176px}header{padding-top:72px;padding-bottom:28px}h1{font-size:48px;letter-spacing:-1.5px;line-height:1.04}.lead{font-size:19px}
.section{padding:12px 20px 10px}.line{padding:12px 20px}.frames{padding:16px 20px 18px 52px}}
@media(max-width:420px){:root{--gutter:14px;--thumb:64px}header{padding-top:36px;padding-bottom:18px}h1{font-size:30px;letter-spacing:-.7px}.lead{font-size:16px}.section{padding:9px 12px 8px}.line{padding:11px 12px;column-gap:10px}.frames{padding:10px 12px 12px 38px}}
"""

LANE_GLYPHS = {
    "visual": '<svg viewBox="0 0 12 12" aria-hidden="true"><rect x="1.5" y="2" width="9" height="8" rx="1" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>',
    "camera": '<svg viewBox="0 0 12 12" aria-hidden="true"><rect x="1" y="3" width="7" height="6" rx="1" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M8 5l3-1.5v5L8 7z" fill="currentColor"/></svg>',
    "text": '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 2.5h8M6 2.5v7M4 9.5h4" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
    "audio": '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M1.5 6h1.5l1.5-3 2 6 1.5-4 1 1h1.5" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
}



def board_size(spec):
    width, height = (int(v) for v in spec["frame"]["aspect"].split(":"))
    scale = 160 / max(width, height)
    return width * scale, height * scale


def board_box(node, width, height):
    return node["x"] * width / 100, node["y"] * height / 100, node["w"] * width / 100, node["h"] * height / 100


def surface_markup(node, x, y, w, h, color):
    shape = node["shape"]
    if shape == "circle":
        return f'<ellipse cx="{x + w / 2:g}" cy="{y + h / 2:g}" rx="{w / 2:g}" ry="{h / 2:g}" fill="{color}"/>'
    if shape == "notch-top-right":
        notch = min(min(w, h) * 0.3, 6)
        points = f"{x:g},{y:g} {x + w - notch:g},{y:g} {x + w:g},{y + notch:g} {x + w:g},{y + h:g} {x:g},{y + h:g}"
        return f'<polygon points="{points}" fill="{color}"/>'
    radius = {"rect": 0, "rounded": min(w, h) * 0.2, "pill": h / 2}[shape]
    return f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{radius:g}" fill="{color}"/>'


def pattern_markup(node, x, y, w, h, ink):
    pattern = node["pattern"]
    if pattern == "none":
        return ""
    size = max(min(h * 0.6, w * 0.18), 0.5)
    ox, oy = x + h * 0.25, y + (h - size) / 2
    attrs = f'stroke="{ink}" stroke-width="{max(size * 0.12, 0.4):g}" fill="none" stroke-linecap="round"'
    if pattern == "vertical":
        return "".join(f'<line x1="{ox + size * k:g}" y1="{oy:g}" x2="{ox + size * k:g}" y2="{oy + size:g}" {attrs}/>' for k in (0.15, 0.5, 0.85))
    if pattern == "horizontal":
        return "".join(f'<line x1="{ox:g}" y1="{oy + size * k:g}" x2="{ox + size:g}" y2="{oy + size * k:g}" {attrs}/>' for k in (0.15, 0.5, 0.85))
    if pattern == "diagonal":
        return "".join(f'<line x1="{ox + size * k:g}" y1="{oy + size:g}" x2="{ox + size * (k + 0.4):g}" y2="{oy:g}" {attrs}/>' for k in (0, 0.3, 0.6))
    if pattern == "chevron":
        return f'<polyline points="{ox:g},{oy + size:g} {ox + size / 2:g},{oy:g} {ox + size:g},{oy + size:g}" {attrs} stroke-linejoin="round"/>'
    return "".join(f'<circle cx="{ox + size * k:g}" cy="{oy + size / 2:g}" r="{size * 0.14:g}" fill="{ink}"/>' for k in (0.2, 0.5, 0.8))


def text_markup(node, x, y, w, h, color):
    size = h * 0.8
    family = "system-ui,'Hiragino Sans','Noto Sans JP',sans-serif"
    return (f'<text x="{x:g}" y="{y + h / 2 + size * 0.36:g}" font-size="{size:g}" font-weight="{TEXT_WEIGHTS[node["weight"]]}" '
            f'font-family="{family}" fill="{color}">{esc(node["content"])}</text>')


def mark(element, dashed=False):
    """One orange stroke, independent of the palette; solid strokes get a thin halo."""
    if dashed:
        return f'<{element} fill="none" stroke="#ff7a1a" stroke-width="1" stroke-dasharray="2.4 1.6"/>'
    return (f'<{element} fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<{element} fill="none" stroke="#ff7a1a" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>')


def arrow_markup(x1, y1, x2, y2):
    length = math.hypot(x2 - x1, y2 - y1)
    if length < 1:
        return ""
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    if length < 12:
        # A short move still needs a readable arrow: keep the tip, extend the tail.
        x1, y1, length = x2 - ux * 12, y2 - uy * 12, 12
    head = 4.5
    bx, by = x2 - ux * head, y2 - uy * head
    px, py = -uy * head * 0.55, ux * head * 0.55
    line = mark(f'line x1="{x1:g}" y1="{y1:g}" x2="{bx:g}" y2="{by:g}"')
    tip = f'polygon points="{x2:g},{y2:g} {bx + px:g},{by + py:g} {bx - px:g},{by - py:g}"'
    return line + f'<{tip} fill="#ff7a1a" stroke="#fff" stroke-width="0.8" stroke-linejoin="round"/>'


def outline_markup(x, y, w, h, dashed):
    return mark(f'rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}"', dashed)


def node_diffs(previous, current, width, height):
    """Classify what changed per node between two frames; boards and chips both read this.
    Yields (kind, old_box, new_box): kind in move / resize / appear / leave / fade."""
    # Version 2 nodes carry a stable key; version 1 nodes are identified by component.
    before = {node.get("key", node["component"]): node for node in previous["nodes"]}
    for node in current["nodes"]:
        box = board_box(node, width, height)
        old = before.pop(node.get("key", node["component"]), None)
        if old is None:
            yield "appear", None, box
            continue
        old_box = board_box(old, width, height)
        x, y, w, h = box
        ox, oy, ow, oh = old_box
        moved = math.hypot((x + w / 2) - (ox + ow / 2), (y + h / 2) - (oy + oh / 2)) >= 1
        resized = abs(w - ow) >= 1 or abs(h - oh) >= 1
        if resized:
            yield "resize", old_box, box
        elif moved:
            yield "move", old_box, box
        if abs(node.get("opacity", 1) - old.get("opacity", 1)) >= 0.05:
            yield "fade", old_box, box
    for old in before.values():
        yield "leave", board_box(old, width, height), None


def annotation_markup(previous, current, width, height):
    """Derive ghosts and arrows from geometry differences; nothing is authored."""
    parts = []
    for kind, old_box, box in node_diffs(previous, current, width, height):
        if kind == "appear":
            parts.append(outline_markup(*box, False))
        elif kind == "move":
            ox, oy, ow, oh = old_box
            x, y, w, h = box
            parts.append(outline_markup(ox, oy, ow, oh, True))
            # Same size, new place: a translation reads as one arrow between centers.
            parts.append(arrow_markup(ox + ow / 2, oy + oh / 2, x + w / 2, y + h / 2))
        elif kind == "resize":
            ox, oy, ow, oh = old_box
            x, y, w, h = box
            parts.append(outline_markup(ox, oy, ow, oh, True))
            # A resize is shown on the edge that traveled; anchored edges stay unmarked.
            # The arrow rides near the edge's far end so it rarely crosses the content inside.
            cx, cy = ox + ow * 0.86, oy + oh * 0.86
            edges = {"left": (ox, x, (ox, cy), (x, cy)), "right": (ox + ow, x + w, (ox + ow, cy), (x + w, cy)),
                     "top": (oy, y, (cx, oy), (cx, y)), "bottom": (oy + oh, y + h, (cx, oy + oh), (cx, y + h))}
            _, _, start, end = max(edges.values(), key=lambda edge: abs(edge[1] - edge[0]))
            parts.append(arrow_markup(*start, *end))
        elif kind == "leave":
            ox, oy, ow, oh = old_box
            parts.append(outline_markup(ox, oy, ow, oh, True))
            inset = min(ow, oh) * 0.25
            parts.append(mark(f'line x1="{ox + inset:g}" y1="{oy + inset:g}" x2="{ox + ow - inset:g}" y2="{oy + oh - inset:g}"'))
            parts.append(mark(f'line x1="{ox + ow - inset:g}" y1="{oy + inset:g}" x2="{ox + inset:g}" y2="{oy + oh - inset:g}"'))
    return "".join(parts)


def change_chips(previous, current, width, height, labels, components=None):
    """Chips naming the kinds of change since the previous frame, in a fixed order.
    With `components`, only nodes of those components are compared (an event's own parts)."""
    if components is not None:
        previous = {"nodes": [n for n in previous["nodes"] if n["component"] in components]}
        current = {"nodes": [n for n in current["nodes"] if n["component"] in components]}
    kinds = {kind for kind, _, _ in node_diffs(previous, current, width, height)}
    return "".join(f'<span class="chip change">{labels[kind]}</span>' for kind in ("move", "resize", "appear", "leave", "fade") if kind in kinds)


def board_svg(spec, frame, reference):
    """Draw one keyframe at the real aspect and background; motion marks are derived
    against the reference keyframe (None for the first state of a sequence)."""
    palette = spec["visual_system"]["palette"]
    width, height = board_size(spec)
    parts = [f'<svg class="frame" viewBox="0 0 {width:g} {height:g}" role="img"><title>{esc(frame["label"])}</title>',
             f'<rect width="{width:g}" height="{height:g}" fill="{palette[spec["frame"]["background"]]}"/>']
    for node in frame["nodes"]:
        x, y, w, h = board_box(node, width, height)
        color = palette[node["fill"]]
        parts.append(f'<g opacity="{node["opacity"]:g}"><title>{esc(node["label"])}</title>')
        if node["kind"] == "text":
            parts.append(text_markup(node, x, y, w, h, color))
        else:
            parts.append(surface_markup(node, x, y, w, h, color) + pattern_markup(node, x, y, w, h, palette[node["pattern_ink"]]))
        parts.append("</g>")
    if reference is not None:
        parts.append(annotation_markup(reference, frame, width, height))
    return "".join(parts) + "</svg>"


def neutral_svg(frame, palette):
    """Version 1 designs carry no aspect, text or pattern; keep their neutral boxes."""
    parts = [f'<svg class="frame" viewBox="0 0 400 240" role="img" style="background:#edf0ed"><title>{esc(frame["label"])}</title>']
    for node in frame["nodes"]:
        x, y, w, h = board_box(node, 400, 240)
        parts.append(f'<g><title>{esc(node["label"])}</title><rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" fill="{palette[node["fill"]]}" stroke="#899c9d"/></g>')
    return "".join(parts) + "</svg>"


def event_rows(spec, review):
    """Rows of the log: each event of each reviewed section, in start order within its
    section, with the keyframes of its own time range. A frame index pair marks the range."""
    scenes = {scene["id"]: scene for scene in spec["scenes"]}
    rows = []
    for section in review["sections"]:
        scene = scenes[section["scene"]]
        events = sorted((e for e in scene["events"] if e["id"] in section["event_ids"]), key=lambda e: (e["start"], LANES.index(e["lane"])))
        for event in events:
            frames = [frame for frame in scene["keyframes"] if event["start"] <= frame["at"] <= event["end"]]
            rows.append({"section": section["id"], "event": event, "frames": frames, "key": event["id"]})
    # An event reviewed across several sections gets one row per section; the underscore
    # separator cannot appear in an id, so qualified keys never collide with plain ones.
    counts = {}
    for row in rows:
        counts[row["key"]] = counts.get(row["key"], 0) + 1
    for row in rows:
        if counts[row["key"]] > 1:
            row["key"] = f'{row["event"]["id"]}_{row["section"]}'
    return rows


def component_homes(spec, rows):
    """The row where each component is first drawn; its picture is shown there."""
    homes, samples = {}, {}
    for row in rows:
        key = row["event"]["id"]
        for frame in row["frames"]:
            for node in frame["nodes"]:
                home = homes.setdefault(node["component"], key)
                # Within its first row, the component is pictured at its fullest extent.
                area = samples.get(node["component"], {"w": 0, "h": 0})
                if home == key and node["w"] * node["h"] > area["w"] * area["h"]:
                    samples[node["component"]] = node
    first = rows[0]["event"]["id"] if rows else None
    for component in spec["components"]:
        homes.setdefault(component["id"], first)
    return homes, samples


def part_svg(spec, node):
    """One component drawn alone, from its first on-screen node, on the frame ground."""
    palette = spec["visual_system"]["palette"]
    width, height = board_size(spec)
    _, _, w, h = board_box(node, width, height)
    w, h = max(w, 1), max(h, 1)
    view_w = 120
    view_h = min(max(view_w * h / w, 24), 120)
    scale = min((view_w - 16) / w, (view_h - 16) / h)
    dw, dh = w * scale, h * scale
    x, y = (view_w - dw) / 2, (view_h - dh) / 2
    color = palette[node["fill"]]
    parts = [f'<svg class="part" viewBox="0 0 {view_w:g} {view_h:g}" role="img"><title>{esc(node["label"])}</title>',
             f'<rect width="{view_w:g}" height="{view_h:g}" fill="{palette[spec["frame"]["background"]]}"/>',
             f'<g opacity="{node["opacity"]:g}">']
    if node["kind"] == "text":
        parts.append(text_markup(node, x, y, dw, dh, color))
    else:
        parts.append(surface_markup(node, x, y, dw, dh, color) + pattern_markup(node, x, y, dw, dh, palette[node["pattern_ink"]]))
    return "".join(parts) + "</g></svg>"


def render_review(spec, review, design_sha256, review_sha256):
    """The viewing document: an audit-log style list. Scene headers group one row per
    event; a row shows the event's subject, time, parts, lane and change chips, and a
    thumbnail of its end frame. A row with several frames or newly pictured parts is
    its own disclosure listing every frame of its range. A CSS-only lane filter sits
    above the list. Prose lives in spec.html."""
    for value in (design_sha256, review_sha256):
        require(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value), "invalid design or review identity")
    labels = REVIEW_LABELS[review["language"]]
    unit = labels["unit"]
    palette = spec["visual_system"]["palette"]
    names = {component["id"]: component["name"] for component in spec["components"]}
    rows = event_rows(spec, review)
    homes, samples = component_homes(spec, rows)
    boards = spec["version"] == 2
    width, height = board_size(spec) if boards else (400, 240)
    lanes_present = [lane for lane in LANES if any(row["event"]["lane"] == lane for row in rows)]

    def draw(frame, reference):
        return board_svg(spec, frame, reference) if boards else neutral_svg(frame, palette)

    def chips(frame, reference, components=None):
        return change_chips(reference, frame, width, height, labels, components) if reference is not None else ""

    if boards:
        orientation = "portrait" if height > width else "landscape"
        meta = f'{spec["duration"]:g}{unit} · {esc(spec["frame"]["aspect"])}'
    else:
        orientation, meta = "landscape", f'{spec["duration"]:g}{unit}'
    parts = [f'<!doctype html><html lang="{review["language"]}"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
             f'<title>{esc(review["title"])}</title><style>{REVIEW_CSS}</style></head><body><main class="{orientation}">',
             f'<header class="wrap"><h1>{esc(review["title"])}</h1><p class="lead">{esc(review["summary"])}</p><p class="meta">{meta}</p>']
    if review["issues"]:
        parts.append(f'<div class="decisions"><p class="label">{labels["issues"]}</p><ol class="issues">')
        parts.extend(f'<li data-issue="{issue["index"]}">{esc(issue["summary"])}</li>' for issue in review["issues"])
        parts.append("</ol></div>")
    if boards:
        parts.append(f'<p class="legend">{labels["legend"]}</p>')
    parts.append("</header>")
    # Lane filter: the radios precede the list so `:checked ~` can hide rows without script.
    parts.append('<input class="lane-input" type="radio" name="lane" id="lane-all" checked>')
    parts.extend(f'<input class="lane-input" type="radio" name="lane" id="lane-{lane}">' for lane in lanes_present)
    parts.append(f'<div class="wrap"><div class="filters" role="group" aria-label="{labels["filter"]}"><span class="label">{labels["filter"]}</span><label for="lane-all">{labels["all"]}</label>')
    parts.extend(f'<label for="lane-{lane}">{labels[lane]}</label>' for lane in lanes_present)
    parts.append(f'</div><ol class="log" aria-label="{labels["log"]}">')
    sections = {section["id"]: section for section in review["sections"]}
    current = None
    for index, row in enumerate(rows):
        section, event, frames = sections[row["section"]], row["event"], row["frames"]
        last = index == len(rows) - 1 or rows[index + 1]["section"] != row["section"]
        row_class = "row last" if last else "row"
        if section["id"] != current:
            current = section["id"]
            parts.append(f'<li class="section" id="beat-{current}"><h2>{esc(section["title"])}<span class="chip time when">{section["start"]:g}–{section["end"]:g}{unit}</span></h2>'
                         f'<span class="copy">{esc(section["summary"])}</span></li>')
        first, last = frames[0], frames[-1]
        hero = draw(last, first if len(frames) > 1 else None)
        arrow = "→" if event["kind"] == "change" else "–"
        actors = "・".join(names[c] for c in event["component_ids"])
        tags = (f'<span class="actor">{esc(actors)}</span>' if actors else "") + f'<span class="chip">{labels[event["lane"]]}</span><span class="chip kind">{labels[event["kind"]]}</span>'
        introduced = [component for component in spec["components"] if homes[component["id"]] == event["id"]]
        if len(frames) > 1:
            tags += chips(last, first, set(event["component_ids"]))
        if len(frames) > 1 or introduced:
            tags += f'<span class="chip more">{len(frames)}</span>'
        line = (f'<span class="glyph">{LANE_GLYPHS[event["lane"]]}</span><span class="body"><span class="head"><span class="title">{esc(event["subject"])}</span>'
                f'<span class="at">{event["start"]:g}{arrow}{event["end"]:g}{unit}</span></span><span class="tags">{tags}</span></span><span class="thumb">{hero}</span>')
        if len(frames) == 1 and not introduced:
            parts.append(f'<li class="{row_class} plain" data-lane="{event["lane"]}" id="event-{row["key"]}"><div class="line">{line}</div></li>')
            continue
        parts.append(f'<li class="{row_class}" data-lane="{event["lane"]}"><details id="event-{row["key"]}"><summary class="line">{line}</summary><div class="frames">')
        if len(frames) > 1:
            parts.append(f'<p class="label">{labels["frames"]}</p><ol class="strip">')
            reference = None
            for frame in frames:
                parts.append(f'<li class="frame">{draw(frame, reference)}<span><span class="chip time">{frame["at"]:g}{unit}</span>'
                             f'<span class="fname">{esc(frame["label"])}</span><span class="chips">{chips(frame, reference)}</span></span></li>')
                reference = frame
            parts.append("</ol>")
        if introduced:
            parts.append(f'<div class="parts"><p class="label">{labels["parts"]}</p>')
            for component in introduced:
                picture = part_svg(spec, samples[component["id"]]) if boards and component["id"] in samples else ""
                parts.append(f'<figure>{picture}<figcaption>{esc(component["name"])}</figcaption></figure>')
            parts.append("</div>")
        parts.append("</div></details></li>")
    parts.append('</ol></div><footer class="wrap">')
    if spec["open_items"]:
        parts.append(f'<details id="issues"><summary>{labels["issue_detail"]}</summary><div class="frames-issues"><ol>')
        parts.extend(f"<li>{esc(issue)}</li>" for issue in spec["open_items"])
        parts.append("</ol></div></details>")
    parts.append(f'<p class="ids">{labels["spec"]}<br>Design ID: sha256:{design_sha256}<br>Review ID: sha256:{review_sha256}</p></footer></main></body></html>')
    return "\n".join(parts)


def physical(path):
    require(path.is_absolute(), "path must be absolute")
    require(not any(p.is_symlink() for p in (path, *path.parents)), "symlink path is not allowed")
    require(path == path.resolve(), "use physical normalized path")
    return path


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def invalid_constant(token):
    raise ValueError(f"invalid number: {token}")


def load_json(path):
    source = physical(path)
    require(stat.S_ISREG(source.stat().st_mode), "input must be a regular file")
    with source.open("rb") as stream:
        raw = stream.read(2 * 1024 * 1024 + 1)
    require(len(raw) <= 2 * 1024 * 1024, "input exceeds 2 MiB")
    return raw, json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=invalid_constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--review", type=Path, help="Authored compact overview bound to the design bytes")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--out", type=Path)
    action.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        raw, spec = load_json(args.spec)
        validate(spec)
        design_sha256 = hashlib.sha256(raw).hexdigest()
        review_raw, review_sha256 = None, None
        if args.review:
            review_raw, review = load_json(args.review)
            validate_review(review, spec, design_sha256)
            review_sha256 = hashlib.sha256(review_raw).hexdigest()
            document = render_review(spec, review, design_sha256, review_sha256).encode("utf-8")
            written = render(spec, design_sha256).encode("utf-8")
            result_extra = {"spec_sha256": hashlib.sha256(written).hexdigest()}
        else:
            document = render(spec, design_sha256).encode("utf-8")
            written, result_extra = None, {}
        require(len(document) <= 16 * 1024 * 1024, "document exceeds 16 MiB")
        result = {"status": "discussion-only" if spec["open_items"] else "design-proposal",
                  "design_sha256": design_sha256,
                  "document_sha256": hashlib.sha256(document).hexdigest(),
                  "checks": "structure-only", "approval": "not-established"}
        if review_sha256:
            result["review_sha256"] = review_sha256
        result.update(result_extra)
        if args.out:
            out = physical(args.out)
            require(out.parent.is_dir(), "output parent must exist")
            os.mkdir(out)
            # Receipt last: an interrupted bundle is never a completed publication.
            files = [("design.json", raw), ("timeline.html", document)]
            if review_raw is not None:
                files += [("review.json", review_raw), ("spec.html", written)]
            files.append(("receipt.json", (json.dumps(result, indent=2) + "\n").encode()))
            for name, data in files:
                with (out / name).open("xb") as stream:
                    stream.write(data)
            result["directory"] = str(out)
            result.update({"html": str(out / "timeline.html"), "design": str(out / "design.json"),
                           "receipt": str(out / "receipt.json")})
            if review_raw is not None:
                result["review"] = str(out / "review.json")
                result["spec"] = str(out / "spec.html")
        print(json.dumps(result))
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        print(f"creative-timeline: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
