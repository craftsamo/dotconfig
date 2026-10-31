"""workspace_init: give a machine the Workspaces skeleton its layout describes (``ws-init``).

Creates what is missing and touches nothing that exists: the root, every area of the workspace
layout, ``.inbox/`` and ``.agent/`` at the root, and an empty workspace registry (``.registry/``,
the CSV headers ``wsreg init`` writes) when there is none. No Group, no ``AGENTS.md`` (the private
overlay links its own, and a real file there would block its link), no data. A folder created for
the root or for a sensitive area is private to the user (0700); the rest follow the umask.

``install.sh`` runs it after the private overlay, so an overlay's layout file is already in place;
running it again changes nothing. ``--check`` reports what it would create. Stdlib only and Python
3.9-compatible, like the layout reader it loads by path. Contract: docs/workspace-layout.md.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REGISTRY = HERE.parent / "workspace" / "workspace-registry" / "registry.py"
ROOT_DIRS = (".inbox", ".agent")


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


workspace_layout = _load("hermes_workspace_layout", HERE / "workspace_layout.py")


def plan(layout) -> list:
    """(path, private) for every folder of the skeleton, root first."""
    folders = [(layout.root, True)]
    folders += [(layout.root / a.name, a.sensitive) for a in layout.areas]
    folders += [(layout.root / name, False) for name in ROOT_DIRS]
    return folders


def run(check: bool = False) -> dict:
    layout = workspace_layout.load()
    if os.path.islink(layout.root) and not layout.root.exists():
        raise workspace_layout.LayoutError(f"{layout.root} is a link to something that is gone; fix it first")
    made, kept, refused = [], [], []
    for path, private in plan(layout):
        if path.is_dir():
            kept.append(str(path))
        elif os.path.lexists(path):
            refused.append(f"{path} exists and is not a folder")
        else:
            if not check:
                path.mkdir(mode=0o700 if private else 0o777)
                if private:
                    os.chmod(path, 0o700)     # mkdir's mode is masked by the umask
            made.append(str(path))
    engine = _load("hermes_workspace_init_registry", REGISTRY)
    registry = engine.data_dir(layout.root)        # <root>/.registry, or WSREG_DIR (staging)
    existed = os.path.lexists(registry)
    if existed and not registry.is_dir():
        refused.append(f"{registry} exists and is not a folder")
    elif existed and any(registry.glob("*.csv")):
        kept.append(str(registry))
    elif refused:
        pass                                       # a skeleton that is not whole gets no registry
    else:
        if not check:
            engine.init(layout.root)
            if not existed:                        # only a folder ws-init made becomes private
                os.chmod(registry, 0o700)
        made.append(str(registry))
    return {"root": str(layout.root), "source": str(layout.source) if layout.source else None,
            "made": made, "kept": kept, "refused": refused, "check": check}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ws-init", description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="report what would be created; change nothing")
    parser.add_argument("--json", action="store_true", help="the result as JSON")
    args = parser.parse_args(argv)
    try:
        result = run(check=args.check)
    except (workspace_layout.LayoutError, OSError) as exc:
        print(f"ws-init: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - the registry's own RegistryError
        if type(exc).__name__ != "RegistryError":
            raise
        print(f"ws-init: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        verb = "would create" if args.check else "created"
        for path in result["made"]:
            print(f"{verb}: {path}")
        for problem in result["refused"]:
            print(f"refused: {problem}", file=sys.stderr)
        if not result["made"] and not result["refused"]:
            print(f"ok: {result['root']} has every folder of its layout")
    return 1 if result["refused"] else 0


if __name__ == "__main__":
    sys.exit(main())
