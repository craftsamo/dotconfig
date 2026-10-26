"""Synthetic post-migration trees. Paths here are the actual on-disk layout."""

import hermes_yaml as yaml


CAPABILITIES = ("engineering", "creative", "writing", "research", "search", "marketing")
PHASES = {"plan": "plan", "execute": "execute", "qa": "quality-assurance"}


def entry_text(name, routes=()):
    phase = "chat" if name == "chat-assistant" else PHASES[name.split("-", 1)[0]]
    domain = "" if phase == "chat" else " " + name.rsplit("-", 1)[1]
    data = {
        "name": name,
        "description": phase.replace("-", " ").title() + domain + " entry.",
        "version": "1.0.0",
        "metadata": {"hermes": {"category": "pipeline"}},
    }
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
    up = "../" if phase == "chat" else "../../"
    body += "\n".join(
        f"${{HERMES_SKILL_DIR}}/{up}{path}" for path in paths
    )
    body += "\n</ReadBeforeWork>\n" + "\n".join(routes) + "\n"
    return "---\n" + yaml.safe_dump(data, sort_keys=False) + "---\n" + body


def build_assistant_tree(write, validator):
    write("SKILL.md", "---\nname: assistant-pipeline\nmetadata:\n  hermes:\n"
          "    category: orchestration\n---\n# Kernel\n")
    write("references/workspace-layout.md", "# Layout\n")
    for prefix, phase in PHASES.items():
        extras = ("resident-sessions.md",) if prefix == "execute" else ()
        write(f"references/{phase}/index.md", "\n".join(
            [f"{prefix}-{cap}" for cap in CAPABILITIES] + list(extras)
        ))
        for filename in extras:
            write(f"references/{phase}/{filename}", "# Common\n")
        for cap in CAPABILITIES:
            name = f"{prefix}-{cap}"
            entry = f"{cap}/{prefix}"
            routes = []
            if prefix == "qa":
                names = validator.REQUIRED_QA_CONTRACTS.get(cap, set())
                for filename in names:
                    write(f"{entry}/references/{filename}", "# Contract\n")
                routes = [f"references/{filename}" for filename in sorted(names)]
            write(f"{entry}/SKILL.md", entry_text(name, routes))
    chat_files = ("workspace-ops.md", "message-reply.md", "cron.md", "lookups.md", "whatsapp.md",
                  "signal.md", "discord.md", "telegram.md", "x.md", "note.md", "substack.md",
                  "youtube.md", "google.md", "web3.md", "github.md")
    write("chat/SKILL.md", entry_text(
        "chat-assistant", [f"references/{filename}" for filename in chat_files]
    ))
    for filename in chat_files:
        write(f"chat/references/{filename}", "# Chat\n")
