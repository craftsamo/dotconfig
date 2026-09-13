#!/usr/bin/env python3
"""Opt-in Three/WebGL2 assets and evidence for existing HyperFrames leaves."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

PIPELINE = Path(__file__).resolve().parents[1]
HERMES = Path(__file__).resolve().parents[5]
ENGINE = HERMES / "engines/three-webgl"
RUNTIME = HERMES / "local/three-webgl"
sys.path.insert(0, str(PIPELINE / "create/tour/scripts"))
from tour import command, digest, load, local, require, write  # noqa: E402

MODE = "three-webgl2"
NAMES = ("three-runtime.js", "three-layer.js", "THREE-LICENSE.txt")
DESCRIPTOR = "assets/three-runtime.json"


def enabled(plan):
    if "graphics" not in plan:
        return False
    require(plan["graphics"] == MODE, "graphics must be three-webgl2 when specified")
    require(plan.get("renderer", "hyperframes") == "hyperframes", "Three graphics requires the HyperFrames renderer")
    return True


def installed():
    marker = RUNTIME / "runtime.json"
    require(marker.is_file(), "Three/WebGL runtime is not provisioned; ask the maintainer, never auto-install")
    data = load(marker)
    require(data.get("version") == 1 and data.get("three") == "0.185.1"
            and data.get("esbuild") == "0.28.2" and data.get("hyperframesVersion") == "0.8.35"
            and data.get("gpu") == "software", "unsupported Three runtime identity")
    expected_inputs = {name: digest(ENGINE / name) for name in
                       ("package.json", "package-lock.json", "setup.mjs", "three-layer.js", "audit.mjs")}
    require(data.get("inputs") == expected_inputs, "Three engine source drift; maintainer refresh and fresh preview required")
    require(set(data.get("assets", {})) == set(NAMES), "invalid Three runtime assets")
    require(data["assets"]["three-layer.js"] == expected_inputs["three-layer.js"],
            "Three adapter copy differs from reviewed engine source")
    for name, sha in data["assets"].items():
        require(digest(RUNTIME / "assets" / name) == sha, "Three runtime asset drift: " + name)
    require(digest(RUNTIME / "package-lock.json") == expected_inputs["package-lock.json"], "installed Three lockfile drift")
    return data


def identity():
    data = installed()
    node, browser, cli = (Path(data[name]) for name in ("node", "browser", "hyperframes"))
    require(all(path.is_file() and path.is_absolute() for path in (node, browser, cli)), "Three runtime executable missing")
    require(command([str(node), "--version"]).strip() == data["nodeVersion"], "Three Node version drift")
    require(command([str(browser), "--version"]).strip() == data["browserVersion"]
            and digest(browser) == data["browserHash"], "Three browser identity drift; new preview approval required")
    require(command([str(node), str(cli), "--version"]).strip() == data["hyperframesVersion"], "Three HyperFrames version drift")
    require(data.get("hyperframesHashes") == {name: digest(cli.parent.parent / "dist" / name)
            for name in ("cli.js", "hyperframe.runtime.iife.js")}, "Three HyperFrames code drift")
    return {**data, "controller_sha256": digest(Path(__file__))}


def descriptor(data):
    return {"version": 1, "graphics": MODE, "three": data["three"], "assets": data["assets"]}


def stage(assets):
    assets = Path(assets)
    require(assets.is_absolute() and assets.is_dir() and assets == assets.resolve(), "stage into an existing physical absolute assets directory")
    require(not any(p.is_symlink() for p in (assets, *assets.parents)), "symlink assets directory forbidden")
    data = installed()
    require(not any((assets / name).exists() or (assets / name).is_symlink() for name in (*NAMES, "three-runtime.json")),
            "Three assets already exist; never overwrite authored/frozen source")
    for name in NAMES:
        with (assets / name).open("xb") as stream:
            stream.write((RUNTIME / "assets" / name).read_bytes())
    write(assets / "three-runtime.json", descriptor(data))
    return {"graphics": MODE, "assets": {"assets/" + name: digest(assets / name)
            for name in (*NAMES, "three-runtime.json")}, "media_generation": 0, "approval": False}


def validate_assets(root, plan, markup=None, *, assets=None):
    selected = enabled(plan)
    directory = assets if assets is not None else root / "assets"
    reserved = {*NAMES, "three-runtime.json"}
    if not selected:
        require(not any((directory / name).exists() for name in reserved), "Three assets need explicit graphics selection in the approved plan/form")
        require(markup is None or not markup.roots[0].get("data-hermes-graphics"), "graphics root requires explicit plan selection")
        return set()
    data = installed()
    require(load(local(str(directory / "three-runtime.json"), {".json"})) == descriptor(data), "Three descriptor differs from the installed pin")
    for name, sha in data["assets"].items():
        path = directory / name
        require(digest(local(str(path), {path.suffix})) == sha, "Three vendor hash mismatch: " + name)
    if markup is not None:
        require(len(markup.canvases) == 1, "one Three canvas required")
        require(markup.roots[0].get("data-hermes-graphics") == MODE, "root must explicitly declare data-hermes-graphics")
        for name in ("assets/three-runtime.js", "assets/three-layer.js"):
            require(markup.assets.count(name) == 1, "load each pinned Three script exactly once")
    return {"assets/" + name for name in NAMES}


def check_authored_code(content):
    require(not re.search(r"\bsetAnimationLoop\s*\(|\b(?:__hfThreeRender|__hermesThreeAudit)\s*=", content),
            "Three authoring must not introduce an animation clock or replace audited hooks")


def execute(argv, *, cwd, timeout, env=None, error_markers=(), stderr_path=None):
    """The new browser child owns its process group; timeout cannot leave it running."""
    child = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, start_new_session=True)
    try:
        stdout, stderr = child.communicate(timeout=timeout)
    except BaseException as error:
        try:
            os.killpg(child.pid, signal.SIGTERM)
            stdout, stderr = child.communicate(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = child.communicate()
        error.evidence = stdout + stderr
        if stderr_path is not None and stderr:
            with stderr_path.open("x", encoding="utf-8") as stream:
                stream.write(stderr)
        raise
    if stderr_path is not None and stderr:
        with stderr_path.open("x", encoding="utf-8") as stream:
            stream.write(stderr)
    if child.returncode or any(marker in stdout + stderr for marker in error_markers):
        error = ValueError(f"Three runtime command failed (exit {child.returncode})")
        error.evidence = stdout + stderr
        raise error
    return stdout


def run_hf(original, root, plan, args, evidence):
    if not enabled(plan):
        return original(root, args, evidence)
    data = identity()
    env = {**os.environ, "HYPERFRAMES_BROWSER_PATH": data["browser"], "PRODUCER_BROWSER_GPU_MODE": "software",
           "DO_NOT_TRACK": "1", "HYPERFRAMES_TELEMETRY_DISABLED": "1"}
    try:
        result = execute([data["node"], data["hyperframes"], *args], cwd=root, timeout=1800, env=env,
                         error_markers=("HermesThree:", "Three layer retained an earlier render error", "[Browser:ERROR]", "[Browser:PAGEERROR]"),
                         stderr_path=evidence.with_suffix(evidence.suffix + ".stderr.log"))
    except Exception as error:
        evidence.write_text(getattr(error, "evidence", str(error)), encoding="utf-8")
        raise
    evidence.write_text(result, encoding="utf-8")


def audit(root, plan, times, out):
    if not enabled(plan):
        return
    data = identity()
    target = out / "graphics.json"
    require(not target.exists(), "graphics evidence already exists")
    try:
        output = execute([data["node"], str(ENGINE / "audit.mjs"), str(root), json.dumps(times), str(target)],
                         cwd=root, timeout=300, env={**os.environ, "DO_NOT_TRACK": "1", "HYPERFRAMES_TELEMETRY_DISABLED": "1"},
                         stderr_path=out / "graphics.stderr.log")
    except Exception as error:
        (out / "graphics.log").write_text(getattr(error, "evidence", str(error)), encoding="utf-8")
        raise
    (out / "graphics.log").write_text(output, encoding="utf-8")
    proof = load(target)
    require(proof.get("status") == "PASS" and {float(t) for t in proof.get("frames", {})} == set(times)
            and all(re.fullmatch(r"[a-f0-9]{64}", h) for h in proof["frames"].values()),
            "Three audit is incomplete")


def bind_preview(preview, plan, out):
    if enabled(plan):
        preview["graphics"] = {"runtime": identity(), "proof": digest(out / "graphics.json")}


def verify_preview(preview, plan, directory):
    if not enabled(plan):
        require("graphics" not in preview, "graphics preview cannot be silently reinterpreted as DOM-only")
        return
    saved = preview.get("graphics", {})
    require(saved.get("runtime") == identity(), "Three runtime changed since preview; fresh preview approval required")
    require(saved.get("proof") == digest(local(str(directory / "graphics.json"), {".json"})), "Three preview evidence changed")


def compare_final(plan, preview_dir, out):
    if enabled(plan):
        before, after = load(preview_dir / "graphics.json"), load(out / "graphics.json")
        require(before["frames"] == after["frames"] and before["renderer"] == after["renderer"],
                "Three layer differs from approved preview; never silently weaken pixel equality")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", required=True, help="Existing new source assets directory")
    args = parser.parse_args()
    try:
        print(json.dumps(stage(args.assets), indent=2))
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
