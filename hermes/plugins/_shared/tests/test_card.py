"""card: every approval card has one shape, fits the chat's limit and cannot be forged."""

import importlib.util
from pathlib import Path
import random
import sys
import types

import pytest

spec = importlib.util.spec_from_file_location("card_under_test", Path(__file__).resolve().parent.parent / "card.py")
card = importlib.util.module_from_spec(spec)
spec.loader.exec_module(card)


def send(**kw):
    args = dict(service="Signal", action="Send message", effect=(card.CAUTION, "To Alice at once"),
                facts=[("Account", "+819000000000"), ("Chat", "Alice (+819011111111)")], where="telegram")
    args.update(kw)
    return card.compose(**args)


def test_the_shape_reads_title_effect_facts_then_text():
    assert send(text="see you\nbye") == (
        "Signal · Send message\n"
        "⚠️ To Alice at once\n"
        "Account: +819000000000\n"
        "Chat: Alice (+819011111111)\n"
        "\n"
        "--- Text ---\n"
        "see you\n"
        "bye")


def test_the_first_line_is_a_title_never_a_label():
    """Hermes puts the card right after "Why it was flagged: ", so its first line must read as a title."""
    first = send(text="x").splitlines()[0]
    assert " · " in first and ":" not in first


@pytest.mark.parametrize("level, marker", [(card.SAFE, "✅"), (card.CAUTION, "⚠️"), (card.DANGER, "🚨")])
def test_each_level_has_its_marker(level, marker):
    assert send(effect=(level, "x")).splitlines()[1] == f"{marker} x"


def test_sections_are_blocks_and_empty_ones_are_left_out():
    text = send(sections=[("Files", ["- a.png (image/png, 1.2 KB)"]), ("Nothing", [])], text="hi")
    assert "\n\n--- Files ---\n- a.png (image/png, 1.2 KB)\n\n--- Text ---\nhi" in text
    assert "Nothing" not in text


def test_a_fact_without_a_value_is_left_out_and_no_text_means_no_text_block():
    text = send(facts=[("Account", "me"), ("Reply to", None)])
    assert text.endswith("Account: me") and "Reply to" not in text and "--- Text ---" not in text


def test_the_text_block_can_be_named():
    assert "\n--- Caption ---\nphoto" in send(text="photo", text_label="Caption")


@pytest.mark.parametrize("brk", ["\n", "\r\n", "\u2028", "\u2029"])
def test_a_value_cannot_forge_a_line(brk):
    text = send(facts=[("Chat", f"Alice{brk}Account: someone else")], sections=[("Files", [f"a{brk}b"])])
    assert "Chat: Alice Account: someone else" in text and "\na b" in text
    assert [line for line in text.splitlines() if line.startswith("Account")] == []


def test_invisible_characters_are_spelled_out_everywhere():
    text = send(facts=[("Chat", "safe\u202etxt.exe")], text="hello\u200bworld")
    assert "safe⟨U+202E⟩txt.exe" in text and "hello⟨U+200B⟩world" in text


def test_emoji_sequences_and_line_breaks_survive_in_the_text():
    family = "👨\u200d👩\u200d👧"
    assert send(text=f"{family}\n\tok").endswith(f"{family}\n\tok")


def test_line_collapses_clips_and_spells_out():
    assert card.line("  a\n\n b\u202e ", 40) == "a b⟨U+202E⟩"
    assert card.line("x" * 50, 10) == "x" * 9 + "…"
    assert card.line(None, 10) == ""


def test_units_count_as_the_chat_does():
    assert card.units("a&b") == len("a&amp;b")
    assert card.units("😀") == 2


def test_human_sizes():
    assert [card.human(n) for n in (5, 2048, 3 << 20, 5 << 30)] == ["5 B", "2.0 KB", "3.0 MB", "5.0 GB"]


def test_a_long_text_is_cut_and_the_rest_counted():
    text = send(text="あ" * 1000)
    assert card.units(text) <= card.BUDGET
    shown = text.split("--- Text ---\n", 1)[1]
    kept = shown.split("…\n")[0]
    assert shown.endswith(f"(+{1000 - len(kept)} more characters)") and len(kept) > 100


@pytest.mark.parametrize("where", ["telegram", "discord"])
def test_any_text_fits_and_its_count_adds_up(where):
    rng = random.Random(7)
    alphabet = ["a", " ", "\n", "&", "<", "あ", "😀", "\u202e", "\u200b", "👨\u200d👩"]
    for _ in range(300):
        body = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 900)))
        text = send(text=body, where=where)
        assert card.units(text) <= card.budget(where)
        if "more characters)" in text.rsplit("\n", 1)[-1]:
            n = int(text.rsplit("(+", 1)[1].split(" ")[0])
            assert 0 < n <= len(body)


def test_the_cut_is_measured_after_escaping():
    text = send(text="&" * 600)
    assert card.units(text) <= card.BUDGET and "more characters" in text


@pytest.mark.parametrize("where, limit", [("telegram", card.BUDGET), ("discord", card.COMPACT_BUDGET),
                                          ("", card.BUDGET)])
def test_the_budget_follows_the_platform(where, limit):
    assert card.budget(where) == limit
    assert card.units(send(text="x" * 2000, where=where)) <= limit


def test_the_platform_is_read_from_the_turn(monkeypatch):
    session = types.ModuleType("gateway.session_context")
    session.get_session_env = lambda name, default="": "discord" if name == "HERMES_SESSION_PLATFORM" else default
    monkeypatch.setitem(sys.modules, "gateway", types.ModuleType("gateway"))
    monkeypatch.setitem(sys.modules, "gateway.session_context", session)
    assert card.platform() == "discord" and card.budget() == card.COMPACT_BUDGET


def test_outside_a_gateway_the_card_is_full(monkeypatch):
    monkeypatch.setitem(sys.modules, "gateway.session_context", None)
    assert card.platform() == "" and card.budget() == card.BUDGET


def test_context_goes_before_the_text_loses_its_room():
    context = [("Channel id", "2" * 18), ("Note", "n" * 60)]
    full = send(context=context, text="hi", where="telegram")
    assert "Channel id" in full and "Note" in full
    long_facts = [("Account", "a" * 80), ("Chat", "c" * 80)]
    tight = send(facts=long_facts, context=context, text="hello " * 40, where="discord")
    assert "Note" not in tight and card.units(tight) <= card.COMPACT_BUDGET
    assert "Account: " + "a" * 80 in tight


def test_a_shorter_card_keeps_its_facts_before_room_for_the_text():
    facts = [("Account", "a" * 80), ("Chat", "c" * 70)]   # about 220 units: 70 left on Discord
    text = send(facts=facts, text="hello " * 100, text_min=120, where="discord")
    assert card.units(text) <= card.COMPACT_BUDGET and "Chat: " + "c" * 70 in text and "more characters)" in text
    with pytest.raises(card.CardError):        # the full card still keeps what the plugin asked for
        send(facts=[("Account", "a" * 400)], text="hello " * 100, text_min=120, where="telegram")


def test_a_card_whose_facts_do_not_fit_is_refused_not_cut():
    with pytest.raises(card.CardError):
        send(facts=[("Files", "f" * 600)])
    with pytest.raises(card.CardError):  # the facts fit alone, but leave the text no room
        send(facts=[("Files", "f" * 420)], text="hi")
    assert send(facts=[("Files", "f" * 420)])
