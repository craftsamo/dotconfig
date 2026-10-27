"""Which model a run uses: the caller's choice, the role's pin or the agent's pin,
checked against the service's catalog and never the caller's own model."""

from __future__ import annotations

import contextlib
import importlib.util
from pathlib import Path
import re
import sys
import time


def _load(name, filename):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


api = _load("hermes_opencode_api", "api.py")
config = _load("hermes_opencode_config", "config.py")

# Speed tiers and dated snapshots serve the same weights as the plain model.
MODEL_ALIAS = re.compile(r"(?:-(?:fast|ultrafast)|-\d{8}|:free)+\Z")
# The main model each Hermes session last answered with (post_api_request), so a
# fallback model counts as the caller's own as well as the configured one.
CALLER_MODELS = {}
CALLER_MODELS_LIMIT = 512
CATALOG_RETRY = 2.0


def model_key(name):
    """A model's identity across providers and speed tiers: anthropic/claude-opus-5-5,
    claude-opus-5-5-fast and a dated snapshot are one model."""
    return MODEL_ALIAS.sub("", str(name).rsplit("/", 1)[-1].lower())


def observe(**payload):
    """post_api_request: remember which main model this Hermes session runs on now."""
    session, model = payload.get("session_id"), payload.get("model")
    if isinstance(session, str) and session and isinstance(model, str) and model:
        CALLER_MODELS.pop(session, None)
        CALLER_MODELS[session] = model
        while len(CALLER_MODELS) > CALLER_MODELS_LIMIT:
            CALLER_MODELS.pop(next(iter(CALLER_MODELS)), None)


def caller_models(home, session):
    """The caller's own models: the configured main model and the one it last answered with."""
    names = set()
    with contextlib.suppress(Exception):
        names.add((config.read(home).get("model") or {}).get("default"))
    names.add(CALLER_MODELS.get(session or ""))
    return {model_key(name) for name in names if isinstance(name, str) and name}


def selection(args, settings, role):
    """Caller-requested model/variant: any model of an allowed provider; the model and
    its variant are checked against the service's catalog at setup.

    A request outside the allowed providers is refused rather than silently replaced:
    the caller asked for a specific engine, and another one would return a result that
    is not the one asked for."""
    chosen = {}
    for key, pattern in (("model", config.MODEL_NAME), ("variant", config.VARIANT_NAME)):
        value = args.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not pattern.fullmatch(value):
            raise ValueError(f"{key} must be a plain name" + (" in provider/model form" if key == "model" else ""))
        if key == "model" and value.split("/", 1)[0] not in settings["allowed_providers"]:
            raise ValueError(f"model {value!r} is not from opencode.allowed_providers "
                             f"{settings['allowed_providers']}; pick one from opencode_catalog models")
        chosen[key] = value
    if "variant" in chosen and "model" not in chosen and not role.get("model"):
        # A variant is provider-specific reasoning effort; it binds to a model the
        # caller or the maintainer chose, never to whatever the agent pins.
        raise ValueError("variant requires a model (explicit or configured for this role)")
    return chosen


def catalog(directory):
    return api.data(api.call("get", api.path("/api/model", api.location(directory))), list)


def identity(entry):
    """The real provider and model behind a catalog entry. An alias model names its
    real one as `modelID` and a provider that is a stop of another (a Console credit
    lane) names it as `canonical`, so every stop of one model shares an identity."""
    return (entry.get("canonical") or entry.get("providerID"), entry.get("modelID") or entry.get("id"))


def _entry(entries, model):
    return next((m for m in entries if m.get("providerID") == model.get("providerID") and m.get("id") == model.get("id")),
                None)


def keep_stop(current, wanted, directory):
    """The model a continuing turn sends: the session's current one when it is another
    stop of the wanted model (OpenCode moved it there on a limit, and sending the wanted
    spelling back would move it again and pay a refused request and a cache rewrite);
    the wanted one otherwise, variant included."""
    if not isinstance(current, dict) or not current.get("id") or not current.get("providerID"):
        return wanted
    if (current["providerID"], current["id"]) == (wanted["providerID"], wanted["id"]):
        return wanted
    entries = catalog(directory)
    now, want = _entry(entries, current), _entry(entries, wanted)
    if now is None or want is None or identity(now) != identity(want):
        return wanted
    # The stop must be able to run this turn as the wanted model was checked to: a lane
    # may lack a variant the subscription offers.
    variant = wanted.get("variant")
    variants = [v.get("id") for v in now.get("variants") or [] if isinstance(v, dict)]
    if (now.get("capabilities") or {}).get("tools") is not True or now.get("enabled") is False or \
            (variant and variant not in variants):
        return wanted
    return {"providerID": current["providerID"], "id": current["id"], **({"variant": variant} if variant else {})}


def engine(role, chosen, info, directory, caller=frozenset()):
    """The provider model reference for this turn.

    Order: the caller's explicit model, then the role's configured pin, then the
    agent's own pin. Raises when the model is the caller's own, unknown to the
    service, unable to use tools, or has no such variant."""
    pin = config.pinned(role.get("model")) if role.get("model") else None
    if role.get("model") and not pin:
        raise ValueError("Invalid configured OpenCode model")
    explicit = chosen.get("model") or (pin or (None,))[0]
    variant = chosen.get("variant") or (None if chosen.get("model") or not pin else pin[1])
    if explicit:
        provider, model = explicit.split("/", 1)
    else:
        if variant:
            raise ValueError("variant has no model to bind to; pass model explicitly")
        agent_pin = info.get("model") or {}
        provider, model, variant = agent_pin.get("providerID"), agent_pin.get("id"), agent_pin.get("variant")
        if not provider or not model:
            raise ValueError(f"OpenCode agent {info.get('id')} pins no model and none is configured")
    if variant is not None and not config.VARIANT_NAME.fullmatch(variant):
        raise ValueError("Invalid OpenCode variant")
    refused = (f"{provider}/{model} is your own model, so it would judge or build what you then "
               "check yourself; pass model= another one from opencode_catalog models (no run launched)")
    if model_key(model) in caller and role.get("caller_model") != "allow":
        raise ValueError(refused)
    entry = None
    for attempt in range(2):
        # The catalog is per location (project config may add providers) and can
        # briefly lack a provider while it reloads, so a miss is checked twice.
        entry = next((m for m in catalog(directory) if m.get("providerID") == provider and m.get("id") == model),
                     None)
        if entry is not None or attempt:
            break
        time.sleep(CATALOG_RETRY)
    if entry is None:
        raise ValueError(f"OpenCode does not offer {provider}/{model}; no run launched")
    # An alias (another login's spelling of the same model) is the caller's own too.
    if model_key(identity(entry)[1]) in caller and role.get("caller_model") != "allow":
        raise ValueError(refused)
    if (entry.get("capabilities") or {}).get("tools") is not True or entry.get("enabled") is False:
        raise ValueError(f"OpenCode model {provider}/{model} cannot run an agent (no tool use); no run launched")
    variants = [v.get("id") for v in entry.get("variants") or [] if isinstance(v, dict)]
    if variant and variant not in variants:
        raise ValueError(f"OpenCode model {provider}/{model} has no variant {variant!r}; no run launched")
    return {"providerID": provider, "id": model, **({"variant": variant} if variant else {})}


def listing(settings, roles, caller):
    """What a caller may pass as model=: tool-capable models of the allowed providers,
    each role's default and alternate, and the caller's own models (refused unless the
    role allows them)."""
    allowed = settings["allowed_providers"]
    models = api.data(api.call("get", "/api/model"), list)
    if not models:
        time.sleep(CATALOG_RETRY)
        models = api.data(api.call("get", "/api/model"), list)
    agents = {a.get("id"): a.get("model") or {} for a in api.data(api.call("get", "/api/agent"), list)}
    defaults = {}
    for name, role in sorted(roles.items()):
        pin = agents.get(role["agent"]) or {}
        defaults[name] = role.get("model") or (
            f"{pin.get('providerID')}/{pin.get('id')}" + (f"#{pin['variant']}" if pin.get("variant") else "")
            if pin.get("id") else None)
    out = []
    for entry in models:
        if entry.get("providerID") not in allowed or entry.get("enabled") is False or \
                (entry.get("capabilities") or {}).get("tools") is not True:
            continue
        cost = (entry.get("cost") or [{}])[0] or {}
        real = identity(entry)
        out.append({
            "model": f"{entry['providerID']}/{entry['id']}", "name": entry.get("name"),
            "variants": [v.get("id") for v in entry.get("variants") or [] if isinstance(v, dict)],
            "context": (entry.get("limit") or {}).get("context"),
            "cost_per_mtok": {k: cost.get(k) for k in ("input", "output")} if cost else None,
            **({"stop_of": f"{real[0]}/{real[1]}"} if real != (entry["providerID"], entry["id"]) else {}),
            **({"yours": True} if model_key(entry["id"]) in caller or model_key(real[1]) in caller else {})})
    alternates = {name: role["alternate"] for name, role in sorted(roles.items()) if role.get("alternate")}
    allowing = sorted(name for name, role in roles.items() if role.get("caller_model") == "allow")
    return {"allowed_providers": allowed, "defaults": defaults, "alternates": alternates,
            "allow_yours": allowing, "models": sorted(out, key=lambda m: m["model"]),
            "note": "Pass model= (and optionally variant= from its variants) to an opencode_run_<role> tool. "
                    "Models marked yours are your own and are refused, except for the roles in allow_yours. "
                    "A model with stop_of is the same model served from another login or a credit lane; "
                    "OpenCode moves a session between such stops itself on a limit, and a continuing turn "
                    "keeps the stop it is on. After a limit error on every stop, rerun on that role's "
                    "alternate (pass it as model= and variant=)."}
