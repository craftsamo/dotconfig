"""tool_preview: the one-line preview Hermes shows for a call of a plugin tool.

Hermes builds a progress line (Telegram, CLI) from a tool's arguments. With no builder
of its own for a tool it takes the first argument named like `query`, `text`, `path` or
`name`, so a message body, a search or a local path reaches the line as written, and a
tool with none of those names shows only `tool...`. A plugin installs its tools' builders
here instead. Hermes offers no hook for this: the builders go into
`agent.display._PREVIEW_BUILDERS`, one table for every profile in the gateway process.
A missing table or a name Hermes already previews is logged and left alone; the tool
keeps working with Hermes' own line.

A preview names the operation, never what it carries: only values a tool's schema
declares as choices (`enum`) pass `allowed`, so free text cannot reach the line. A tool
registered by several profiles with different choices keeps their union.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Set on every builder installed here, so a reinstall replaces ours and never Hermes' own.
MARK = "_hermes_plugin_preview"
# tool -> parameter -> declared choices, merged across the profiles that register the tool.
_CHOICES: dict[str, dict[str, set[str]]] = {}


def choices(schema, key):
    """The string choices a tool schema declares for `key` (or for its array items)."""
    parameters = (schema or {}).get("parameters", schema) or {}
    spec = (parameters.get("properties") or {}).get(key) or {}
    values = spec.get("enum") or (spec.get("items") or {}).get("enum") or ()
    return {value for value in values if isinstance(value, str)}


def allowed(tool, key, value):
    """`value` when it is one of the choices recorded for `tool`'s `key`, else None."""
    if isinstance(value, str) and value in _CHOICES.get(tool, {}).get(key, ()):
        return value
    return None


def _clip(text, max_len):
    if not isinstance(text, str) or not text:
        return None
    return text if not max_len or len(text) <= max_len else text[:max(1, max_len - 1)] + "…"


def install(tool, build, schema=None, keys=()):
    """Show `build(args)` as `tool`'s preview; record `schema`'s choices for `keys` first.

    `build` returns a short label or None (Hermes then shows the bare tool name). Returns
    whether the builder is in place."""
    for key in keys:
        _CHOICES.setdefault(tool, {}).setdefault(key, set()).update(choices(schema, key))
    try:
        from agent import display

        builders = display._PREVIEW_BUILDERS
    except Exception as exc:
        logger.warning("tool preview for %s not installed: %s", tool, exc)
        return False
    current = builders.get(tool)
    if current is not None and not getattr(current, MARK, False):
        logger.warning("tool preview for %s not installed: Hermes already previews it", tool)
        return False

    def preview(args, max_len):
        try:
            return _clip(build(args if isinstance(args, dict) else {}), max_len)
        except Exception as exc:
            logger.debug("tool preview for %s failed: %s", tool, exc)
            return None

    setattr(preview, MARK, True)
    builders[tool] = preview
    return True


def enums(tool, schema, *keys):
    """Install a preview joining the declared choice of each of `keys` a call carries,
    e.g. `send` or `quote transfer`."""
    def build(args):
        return " ".join(value for value in (allowed(tool, key, args.get(key)) for key in keys) if value) or None
    return install(tool, build, schema, keys)


def fixed(tool, label):
    """Install a preview that is always `label`, for a tool whose arguments are all content."""
    return install(tool, lambda args: label)
