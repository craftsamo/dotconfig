"""Synthetic post-migration trees. Paths here are the actual on-disk layout."""

import yaml


CAPABILITIES = ("engineering", "creative", "writing", "research", "search", "marketing")
PHASES = {"plan": "plan", "execute": "execute", "qa": "quality-assurance"}
CARDS = {
    "execute-assistant-creative": {
        "anchored-image-batch": "creator", "deterministic-render": "creator"
    },
    "execute-assistant-search": {
        "survey-enumeration": "searcher", "exhaustive-hunt": "searcher"
    },
}


def entry_text(name, routes=()):
    phase = "chat" if name == "chat-assistant" else PHASES[name.split("-", 1)[0]]
    domain = "" if phase == "chat" else " " + name.rsplit("-", 1)[1]
    data = {
        "name": name,
        "description": phase.replace("-", " ").title() + domain + " entry.",
        "version": "1.0.0",
        "metadata": {"hermes": {"category": "assistant-pipeline"}},
    }
    if name in CARDS:
        data["card_units"] = [
            {"name": unit, "assignee": assignee, "required_inputs": ["spec"],
             "unit_cap": "one", "runtime_cap": 900}
            for unit, assignee in CARDS[name].items()
        ]
    paths = ["SKILL.md"]
    calls = ['skill_view(name="assistant-pipeline")']
    if phase != "chat":
        paths.append(f"references/{phase}/index.md")
        calls.append(f'skill_view(name="assistant-pipeline", file_path="{paths[-1]}")')
    body = "<ReadBeforeWork>\n" + "\n".join(calls) + "\n"
    body += (
        "Read the full body of each dependency before work. Reuse only the full body\n"
        "already in this context, not a past summary. If unchanged and the earlier\n"
        "full body is missing, use read_file on the canonical paths below;\n"
        "stop if unavailable.\n"
    )
    body += "\n".join(
        f"${{HERMES_SKILL_DIR}}/../{path}" for path in paths
    )
    body += "\n</ReadBeforeWork>\n" + "\n".join(routes) + "\n"
    return "---\n" + yaml.safe_dump(data, sort_keys=False) + "---\n" + body


def build_assistant_tree(write, validator):
    write("SKILL.md", "---\nname: assistant-pipeline\nmetadata:\n  hermes:\n"
          "    category: orchestration\n---\n# Kernel\n")
    for prefix, phase in PHASES.items():
        extras = ("resident-sessions.md", "kanban-lite.md", "scheduled.md") if prefix == "execute" else ()
        write(f"references/{phase}/index.md", "\n".join(
            [f"{prefix}-assistant-{cap}" for cap in CAPABILITIES] + list(extras)
        ))
        for filename in extras:
            write(f"references/{phase}/{filename}", "# Common\n")
        for cap in CAPABILITIES:
            name = f"{prefix}-assistant-{cap}"
            routes = []
            if cap == "creative" and prefix != "qa":
                write(f"{name}/references/legacy/index.md", "# Retained references\n")
                routes = ["references/legacy/index.md"]
            if prefix == "qa":
                names = validator.REQUIRED_QA_CONTRACTS.get(cap, set())
                shelf = "references/legacy" if cap == "creative" else "references"
                for filename in names:
                    write(f"{name}/{shelf}/{filename}", "# Contract\n")
                if cap == "creative":
                    write(f"{name}/{shelf}/index.md", " ".join(sorted(names)))
                    routes = ["references/legacy/index.md"]
                else:
                    routes = [f"references/{filename}" for filename in sorted(names)]
            write(f"{name}/SKILL.md", entry_text(name, routes))
    chat_files = ("workspace-ops.md", "cron.md", "lookups.md")
    write("chat-assistant/SKILL.md", entry_text(
        "chat-assistant", [f"references/{filename}" for filename in chat_files]
    ))
    for filename in chat_files:
        write(f"chat-assistant/references/{filename}", "# Chat\n")
