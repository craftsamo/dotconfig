#!/usr/bin/env python3
"""Task-owned illustrative UI fixture, not a production layout/preset engine."""
import argparse
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

LEAF = Path(__file__).resolve().parents[4] / "profiles/video-creator/skills/video-creator-pipeline/create/tour"
sys.path.insert(0, str(LEAF / "scripts"))
import authored

CUSTOM_INTRO = "Two Light and Dark tiles slide together into one settings window, like closing a book."
CUSTOM_OUTRO = "Fold the settings window back into two comparison tiles; underline the chosen Dark tile."


def fixture(root, variant="main"):
    authored.require(variant in ("main", "overview", "result", "custom", "none"), "unknown fixture, no fallback")
    root = authored.fresh(str(root))
    root.mkdir()
    source = root / "source"
    (source / "assets").mkdir(parents=True)
    for name in ("gsap.min.js", "GSAP-LICENSE.txt", "gsap-provenance.json"):
        shutil.copyfile(LEAF / "assets" / name, source / "assets" / name)
    duration = 20 if variant == "main" else 8
    intro = "title-reveal"
    outro = "result-hold"
    opening = "Title docks above the same UI while the window rises into view."
    closing = "Final dark state and saved name stay visible with completion text."
    intro_code = """pose('#heading',{y:230,scale:1.2},0);
pose('#window',{y:650},0);
move('#heading',{y:0,scale:1,duration:.7,ease:'power3.inOut'},1.5);
move('#window',{y:0,duration:.8,ease:'power3.out'},1.7);"""
    outro_code = """pose('#completion',{opacity:1,y:12},17);
move('#completion',{y:0,duration:.6,ease:'power3.out'},17);"""
    if variant == "overview":
        intro, outro = "ui-overview", "overview-close"
        opening = "Whole UI and heading establish context before a pointer-led focus."
        closing = "Camera pulls out from selected Dark state and reveals the completion line."
        intro_code = "move('#window',{scale:1.03,duration:1.2,ease:'power2.inOut'},1.4);"
        outro_code = """pose('#window',{scale:1.1,x:-30},16.9);
move('#window',{scale:1,x:0,duration:1,ease:'power2.inOut'},17);
pose('#completion',{opacity:1,y:12},18);
move('#completion',{y:0,duration:.6,ease:'power3.out'},18);"""
    elif variant == "result":
        intro, outro = "result-first", "next-action"
        opening = "Show Dark first, display rewind cue and visibly restore Light setup."
        closing = "Dock result window slightly up and show approved CTA: choose your own appearance."
        intro_code = """dark(0);
pose('#setup',{opacity:1},.7);
move('#app',{backgroundColor:'#f7fafc',duration:.5},1.8);
move('#sidebar',{backgroundColor:'#e8f0f5',duration:.5},1.8);
move('#panel-title,#setting-name',{color:'#152c3e',duration:.5},1.8);
move('.hint,.nav:not(.active)',{color:'#486477',duration:.5},1.8);
pose('#light-choice',{borderColor:'#246cce'},1.8);pose('#dark-choice',{borderColor:'#bccdd8'},1.8);
pose('#selection',{x:0,color:'#2463bd'},1.8);pose('#selection',{opacity:1},2.6);pose('#setup',{opacity:0},2.6);"""
        outro_code = """move('#window',{y:-15,scale:.97,duration:.7,ease:'power2.inOut'},17);
pose('#completion',{opacity:1,y:-10},17.5);move('#completion',{y:0,duration:.6,ease:'power3.out'},17.5);"""
    elif variant == "custom":
        intro, outro = CUSTOM_INTRO, CUSTOM_OUTRO
        opening, closing = CUSTOM_INTRO, CUSTOM_OUTRO
        intro_code = """pose('#tiles',{opacity:1},0);pose('#window',{opacity:0},0);
move('#tile-light',{x:175,scaleX:.1,duration:.65,ease:'power3.in'},1.3);
move('#tile-dark',{x:-175,scaleX:.1,duration:.65,ease:'power3.in'},1.3);
pose('#tiles',{opacity:0},1.95);pose('#window',{opacity:1,scaleX:.05},1.95);
move('#window',{scaleX:1,duration:.7,ease:'power3.out'},1.95);"""
        outro_code = """move('#window',{scaleX:.05,duration:.65,ease:'power3.in'},17);
pose('#window',{opacity:0},17.65);pose('#tiles',{opacity:1},17.65);
move('#tile-light',{x:0,scaleX:1,duration:.65,ease:'power3.out'},17.65);
move('#tile-dark',{x:0,scaleX:1,duration:.65,ease:'power3.out'},17.65);
pose('#tile-dark',{borderBottom:'8px solid #50d9b1'},18.35);
pose('#completion',{opacity:1,y:-70},18.35);"""
    elif variant == "none":
        intro = outro = "none"
        opening = closing = intro_code = outro_code = ""
    form = {"what_for": "Show choosing Dark and naming the appearance in an illustrative UI",
            "audience": "Japanese-speaking beginners", "fidelity": "simplified",
            "reference": "Text-defined macOS-like settings, Light/Dark previews and illustrative naming modal; not actual OS functionality.",
            "flow": "Choose Dark, open naming modal, type name, save; illustrative only.",
            "style": "flat", "background": "blue-to-mint gradient", "duration": duration,
            "intro": intro, "outro": outro, "preview": "yes"}
    if variant == "result":
        form["note"] = "Approved CTA: 自分に合う見た目を選びましょう。 No URL."
    samples = [(0, "Opening first visible frame"), (1.8, "Opening transition"),
               (2.7, "Opening resolved to setup"), (5.4, "Pointer tip reaches Dark preview"),
               (6.6, "Dark selection updates actual UI colors"), (9.35, "Modal appears while camera pulls back"),
               (10.95, "Partial typed name in modal"), (12.4, "Full name in modal"),
               (14.1, "Pointer contacts Save"), (15.5, "Modal closed; saved name in Dark UI"),
               (17.5, "Closing transition"), (18.7, "Closing result/CTA/custom tiles")]
    contract = {"duration": duration,
                "intro": {"direction": intro, "start": 0, "end": 0 if intro == "none" else 3*duration/20, "description": opening},
                "outro": {"direction": outro, "start": duration if outro == "none" else 17*duration/20, "end": duration, "description": closing},
                "fidelity_note": "Approved simplified illustrative UI, not captured macOS; naming modal is illustrative, not a real macOS feature.",
                "samples": [{"at": t*duration/20, "expect": e} for t, e in samples] + [{"at": duration-1/30, "expect": "Final visible result; no black tail"}]}
    code = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
    code = code.replace("@@DURATION@@", str(duration)).replace("@@INTRO@@", intro_code).replace("@@OUTRO@@", outro_code)
    if variant == "result":
        code = code.replace("ダークに変更できました。", "自分に合う見た目を選びましょう。")
        code = code.replace("#selection{position:", "#selection{opacity:0;position:")
        # Exact zero seek may leave zero-duration tweens unrendered. Match the
        # initial paint to the teaser state, not just HyperFrames' forced seek.
        code = code.replace("</style>", """#app{background:#203b50}#sidebar{background:#182f43}
#panel-title,#setting-name{color:#f3f8ff}.hint,.nav:not(.active){color:#d3e4ef}
#light-choice{border-color:#bccdd8}#dark-choice{border-color:#5fa7ff}
</style>""")
    if variant == "custom":
        code = code.replace("ダークに変更できました。", "自分に合う見た目へ。")
    (source / "index.html").write_text(code, encoding="utf-8")
    authored.write(source / "index.motion.json", {"duration": duration, "assertions": [
        {"kind": "appearsBy", "selector": "#modal", "bySec": 9.6*duration/20}]})
    authored.write(source / "ledger.json", {"seams": [], "note": "Single continuous UI carrier; no inter-scene cuts. Staged reveals, purposeful camera and sequenced UI life."})
    authored.write(root / "form.json", form)
    authored.write(root / "contract.json", contract)
    return form, contract


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--variant", choices=["main", "overview", "result", "custom", "none"], default="main")
    parser.add_argument("--render", action="store_true", help="explicit approval to render this local illustrative fixture")
    args = parser.parse_args()
    fixture(Path(args.root), args.variant)
    if args.render:
        root = Path(args.root)
        authored.freeze(SimpleNamespace(form=str(root / "form.json"), contract=str(root / "contract.json"),
                                        source=str(root / "source"), project=str(root / "project")))
        authored.snapshot(SimpleNamespace(project=str(root / "project"), out=str(root / "preview")))
        authored.render(SimpleNamespace(project=str(root / "project"), out=str(root / "final"),
                                        approved_preview=str(root / "preview")))
    print(json.dumps({"root": args.root, "variant": args.variant, "evidence": "direct local illustrative render only"}))
