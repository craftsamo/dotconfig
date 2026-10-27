"""cron-manifests — the built-in ``cronjob_manage``, with its writes routed through ``cron.d/``.

Same name, same schema, same ``list`` and ``run``; ``create`` writes a manifest directory of the
profile and lets cron-sync make the job, ``update`` rewrites that manifest, ``remove`` deletes it
with its job, and a job tracked in a repository is refused. The body is ``manage.py`` beside this
file; the engine is ``scripts/cron-sync.py``. Contract: docs/ops/cron.md.

Needs ``plugins.entries."guards/cron-manifests".allow_tool_override: true`` in the profile's
config, or Hermes refuses the override and keeps its own tool.
"""

from __future__ import annotations

import copy
import importlib.util
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
HERMES_ROOT = HERE.parents[2]  # plugins/guards/cron-manifests -> hermes/


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


manage = _load("hermes_cron_manifests_manage", HERE / "manage.py")
tool_preview = _load("hermes_tool_preview", HERMES_ROOT / "plugins" / "_shared" / "tool_preview.py")

TOOL = manage.TOOL
PLUGIN = "cron-manifests"

ADDENDUM = (
    "\n\nA job you create is kept as cron.d/<name>/ in this profile (job.yaml, and run.sh when it "
    "runs a script); `name` becomes that directory, so give one. A job tracked in a repository "
    "cannot be updated, paused or removed here — say so to the user; one made before manifests "
    "existed can be removed but not updated. A relative one-shot (`in 30m`) is stored as the "
    "instant it means. Model pins are never set from a chat.")


def schema():
    """The runtime's own schema, with `action` declared as choices (for the progress line) and
    the manifest contract appended to the description."""
    from tools.cronjob_tools import CRONJOB_SCHEMA
    built = copy.deepcopy(CRONJOB_SCHEMA)
    built["description"] = built["description"] + ADDENDUM
    built["parameters"]["properties"]["action"]["enum"] = list(manage.ACTIONS)
    return built


def cronjob_manage(args, **kwargs):
    from hermes_constants import get_hermes_home
    sync = manage.load_sync(HERMES_ROOT)
    return manage.handle(args if isinstance(args, dict) else {}, get_hermes_home(), sync, **kwargs)


def register(ctx):
    from tools.cronjob_tools import check_cronjob_requirements
    built = schema()
    ctx.register_tool(
        name=TOOL, toolset="cronjob", schema=built, handler=cronjob_manage,
        check_fn=check_cronjob_requirements, description=built["description"], emoji="⏰", override=True,
    )
    tool_preview.enums(TOOL, built, "action")
