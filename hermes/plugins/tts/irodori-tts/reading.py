"""Text side of the Irodori-TTS provider: what the model is asked to read.

Irodori has no reading frontend. The server only normalises characters (NFKC,
a few symbol deletions), then a subword tokenizer hands raw kanji, digits and
Latin letters to the model, which guesses the reading. Everything that makes a
reading deterministic therefore has to happen here, before the request.

Kept free of numpy and of Hermes imports on purpose, so the reading checker
(``scripts/irodori_tts_reading_check.py``) can load this file on its own and
measure exactly the text the provider would send.
"""

from __future__ import annotations

import json
import logging
import os
import re
from fractions import Fraction
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Pronunciation lexicon
# --------------------------------------------------------------------------

# The lexicon is DATA, not code, and a pronunciation dictionary tends to
# accumulate names the owner would rather not publish. This repo is public, so
# the file is read from the gitignored runtime directory instead of shipping
# beside the plugin -- the same split qwen3-tts uses for its voice catalog.
# Install it with `launchd/irodori-tts-launchctl.sh register-lexicon --file PATH`.
# No path is read from config.yaml on purpose: config.yaml is tracked, and a
# path into a private tree must not land there.
LEXICON_ENV = "IRODORI_TTS_LEXICON"
_lexicon_cache: Optional[Tuple[Dict[str, str], Optional[re.Pattern]]] = None


def _runtime_dir() -> Path:
    """Locate hermes/local/irodori-tts/ from wherever this plugin was loaded.

    Hermes reads plugins through ~/.hermes/plugins, which is a symlink into the
    config repo, so the path is resolved before walking up. The walk looks for
    the directory that owns config.yaml rather than counting parents, which
    survives the plugin being nested differently.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config.yaml").exists() and (parent / "plugins").is_dir():
            return parent / "local" / "irodori-tts"
    return here.parents[3] / "local" / "irodori-tts"


def lexicon_path() -> Path:
    override = os.environ.get(LEXICON_ENV)
    if override:
        return Path(override).expanduser()
    return _runtime_dir() / "lexicon.json"


def compile_lexicon(terms: Dict[str, str]) -> Optional[re.Pattern]:
    """One alternation, longest key first so "Claude Code" beats "Claude".

    ASCII keys are fenced by ASCII letters and digits only, so "Gemini" does
    not fire inside "GeminiFooBar" yet does fire in "Geminiで". (A plain \b
    would not: Python counts kana and kanji as word characters, so a Latin
    name glued to Japanese -- the normal case -- never matched.) Keys need not
    be Latin: a kanji surface works the same way and pins a reading the model
    keeps guessing wrong.
    """
    if not terms:
        return None
    parts = []
    for key in sorted(terms, key=len, reverse=True):
        esc = re.escape(key)
        if key[0].isascii() and key[0].isalnum():
            esc = r"(?<![A-Za-z0-9])" + esc
        if key[-1].isascii() and key[-1].isalnum():
            esc = esc + r"(?![A-Za-z0-9])"
        parts.append(esc)
    return re.compile("|".join(parts))


def read_lexicon(path: Path) -> Dict[str, str]:
    """Parse ``{"terms": {surface: reading}}``; anything else is ignored."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    candidate = raw.get("terms") if isinstance(raw, dict) else None
    if not isinstance(candidate, dict):
        return {}
    return {
        str(k): str(v)
        for k, v in candidate.items()
        if isinstance(k, str) and isinstance(v, str) and k
    }


def load_lexicon() -> Tuple[Dict[str, str], Optional[re.Pattern]]:
    global _lexicon_cache
    if _lexicon_cache is not None:
        return _lexicon_cache
    terms: Dict[str, str] = {}
    path = lexicon_path()
    try:
        terms = read_lexicon(path)
        logger.debug("irodori-tts: loaded %d lexicon term(s)", len(terms))
    except FileNotFoundError:
        # Optional: without it, proper nouns are simply read as the model sees
        # them.
        logger.debug("irodori-tts: no lexicon at %s; skipping substitution", path)
    except Exception as exc:  # noqa: BLE001 - the lexicon is an optimisation
        logger.warning("irodori-tts: lexicon at %s unreadable (%s); skipping", path, exc)
    _lexicon_cache = (terms, compile_lexicon(terms))
    return _lexicon_cache


def apply_lexicon(
    text: str,
    lexicon: Optional[Tuple[Dict[str, str], Optional[re.Pattern]]] = None,
) -> str:
    """Rewrite known surfaces (Latin proper nouns, stubborn kanji) as kana."""
    terms, pattern = lexicon if lexicon is not None else load_lexicon()
    if not pattern:
        return text
    return pattern.sub(lambda m: terms.get(m.group(0), m.group(0)), text)


# --------------------------------------------------------------------------
# Undoing the shared cleaner's English
# --------------------------------------------------------------------------

# Every Hermes TTS call runs hermes-agent's prepare_spoken_text first, and that
# cleaner is written for English voices: 60% becomes "60 percent", 25°C
# "25 degrees Celsius", 10~20 "10 about 20". Irodori has no English, so those
# words come out mangled in the middle of a Japanese sentence. The cleaner is
# shared and must not be weakened (hermes/AGENTS.md), so its output is mapped
# back to Japanese here, and only where it is unambiguous: a digit or a
# Japanese character next to the inserted word. Real English stays English.

_JA = r"\u3040-\u30FF\u3400-\u9FFF\u3005\uFF10-\uFF19"
_JA_CHAR = rf"[{_JA}]"
_JA_OR_DIGIT = rf"[{_JA}0-9]"
_NUM = r"[-+]?\d[\d,]*(?:\.\d+)?"

_CLEANER_UNITS = (
    ("kilometres per hour", "キロメートル毎時"),
    ("millimetres", "ミリメートル"),
    ("centimetres", "センチメートル"),
    ("kilometres", "キロメートル"),
    ("metres", "メートル"),
)
_CLEANER_CURRENCY = (
    ("New Zealand dollars", "ニュージーランドドル"),
    ("Australian dollars", "豪ドル"),
    ("US dollars", "米ドル"),
    ("dollars", "ドル"),
    ("euros", "ユーロ"),
    ("pounds", "ポンド"),
)


def undo_cleaner_english(text: str) -> str:
    """Map the cleaner's English expansions back to Japanese readings."""
    # Temperatures: a range first ("11 to 17 degrees Celsius"), then singles.
    # Python's \b treats kana and kanji as word characters, so the cleaner's
    # own "°C\b" misses "25°Cで" and leaves "25 degreesCで"; the patterns here
    # end on (?![A-Za-z]) for the same reason.
    text = re.sub(
        rf"(?<![0-9.,])(?:華氏 ?)?({_NUM}) degrees ?(?:Fahrenheit|F)(?![A-Za-z])", r"華氏\1度", text
    )
    text = re.sub(r"(?<=\d) degrees(?: ?(?:Celsius|C)(?![A-Za-z]))?", "度", text)
    text = re.sub(r"(?<![A-Za-z])degrees ?(?:Celsius|C)(?![A-Za-z])", "度", text)
    for word, kana in _CLEANER_UNITS:
        text = re.sub(rf"(?<=\d) {word}(?![A-Za-z])", kana, text)
    for word, kana in _CLEANER_CURRENCY:
        text = re.sub(rf"(?<=\d) {word}(?![A-Za-z])", kana, text)
    text = re.sub(r"(?<=\d) percent(?![A-Za-z])", "パーセント", text)
    # "~" became " about ": a range between numbers, "approximately" before one.
    text = re.sub(rf"(?<=[0-9]) about (?={_NUM})", "から", text)
    text = re.sub(rf"(?:(?<=^)|(?<=[\s{_JA}]))\s*about (?=\d)", "約", text)
    text = re.sub(rf"(?<={_JA_CHAR}) about (?={_JA_OR_DIGIT})", "から", text)
    # "→"/"⇒" became " to ": between numbers a range, otherwise a step.
    text = re.sub(rf"(?<=[0-9]) to (?={_NUM})", "から", text)
    text = re.sub(rf"(?<={_JA_OR_DIGIT}) to (?={_JA_OR_DIGIT})", "、", text)
    text = re.sub(rf"(?<={_JA_CHAR}) and |(?<=\S) and (?={_JA_CHAR})", "アンド", text)
    # Line breaks became ". ", headings ", " and table pipes "; ".
    text = re.sub(rf"(?<=[{_JA}）」』】])\.(?:\s+|$)", "。", text)
    text = re.sub(rf"(?<=[{_JA}）」』】])[,;]\s+", "、", text)
    return text


# --------------------------------------------------------------------------
# Symbols the model reads badly or the server deletes
# --------------------------------------------------------------------------

# Irodori's own normaliser turns 〜/～ into a long-vowel mark and DELETES every
# hyphen and dash, so "-5" arrives as "5" and "10-20" as "1020". Those have to
# be spelled out before the request.
_WAVE = "[〜～~]"
_RANGE_START = r"[0-9A-Za-z\u3400-\u9FFF\u3005]"
_RANGE_END = r"[0-9A-Za-z\u30A0-\u30FF\u3400-\u9FFF\u3005]"
_DIGIT_READ = "ゼロ いち に さん よん ご ろく なな はち きゅう".split()


def _digits_one_by_one(digits: str) -> str:
    return "".join(_DIGIT_READ[int(d)] for d in digits)


def japanese_symbols(text: str) -> str:
    text = text.translate(_FULLWIDTH)
    # Dates written with separators: 2026/10/03, 2026-10-03.
    text = re.sub(
        r"(?<!\d)(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?!\d)",
        lambda m: f"{int(m.group(1))}年{int(m.group(2))}月{int(m.group(3))}日",
        text,
    )
    # Clock times: 10:30 -> 10時30分 (two-digit minutes, so a 3:2 score stays).
    text = re.sub(
        r"(?<![\d:])(\d{1,2}):(\d{2})(?![\d:])",
        lambda m: f"{int(m.group(1))}時" + (f"{int(m.group(2))}分" if int(m.group(2)) else ""),
        text,
    )
    # Phone numbers: digit by digit, groups separated by a pause.
    text = re.sub(
        r"(?<![\d-])(0\d{1,4})-(\d{1,4})-(\d{3,4})(?![\d-])",
        lambda m: "、".join(_digits_one_by_one(g) for g in m.groups()),
        text,
    )
    # Numeric ranges: 10-20, 11–17. Whole numbers only on both sides, so
    # identifiers (UUIDs, a716-4466, RFC-9110) are not read as ranges.
    text = re.sub(
        r"(?<![A-Za-z0-9_.\-‐–—−])(\d+(?:\.\d+)?)\s*[-‐–—−]\s*(?=\d+(?:\.\d+)?(?![A-Za-z0-9_\-‐–—−]|\.\d))",
        r"\1から",
        text,
    )
    # A wave dash after a number, kanji or Latin word opens a range (東京〜大阪,
    # 3〜5分, 東京〜ニューヨーク). After kana -- katakana included, ヤッホ〜 --
    # it is a drawn-out vowel, which the server turns into ー.
    text = re.sub(rf"(?<={_RANGE_START})\s*{_WAVE}\s*(?={_RANGE_END})", "から", text)
    text = re.sub(r"(?<![A-Za-z0-9_.])[-−](?=\d)", "マイナス", text)
    # Yen before the amount, the way it is written but not read.
    text = re.sub(r"[¥￥]\s*(\d[\d,]*)", r"\1円", text)
    text = re.sub(r"\s*[→⇒]\s*", "、", text)
    text = re.sub(r"\s*&\s*", "アンド", text)
    # A full-width colon is a pause in running Japanese.
    text = re.sub(r"\s*：\s*", "、", text)
    text = re.sub(rf"(?<={_JA_CHAR})[:,]\s*", "、", text)
    # "結果：" followed by a list leaves the cleaner's sentence stop behind it.
    text = re.sub(r"、\s*\.(?:\s+|$)", "、", text)
    return text


# --------------------------------------------------------------------------
# Numbers
# --------------------------------------------------------------------------

# Digits are subword noise to the model: 9時 comes out as きゅうじ, 4月 as
# よんがつ, 1日 drifts. Spelling them in kana makes the reading deterministic.
# Ported from the qwen3-tts server's expander (which ships as one standalone
# file into its own venv, so it cannot be imported from here), extended with
# the counters and units an assistant actually says.

_FULLWIDTH = str.maketrans("０１２３４５６７８９．，：％－", "0123456789.,:%-")
_DIGIT_KANA = dict(enumerate("ゼロ いち に さん よん ご ろく なな はち きゅう".split()))


def _kana_group(value: int) -> str:
    """Kana for 1..9999 with euphonic changes (さんびゃく, はっせん...)."""
    parts: list = []
    thousands, rest = divmod(value, 1000)
    hundreds, rest = divmod(rest, 100)
    tens, ones = divmod(rest, 10)
    if thousands:
        parts.append(
            {1: "せん", 3: "さんぜん", 8: "はっせん"}.get(
                thousands, _DIGIT_KANA[thousands] + "せん"
            )
        )
    if hundreds:
        parts.append(
            {1: "ひゃく", 3: "さんびゃく", 6: "ろっぴゃく", 8: "はっぴゃく"}.get(
                hundreds, _DIGIT_KANA[hundreds] + "ひゃく"
            )
        )
    if tens:
        parts.append("じゅう" if tens == 1 else _DIGIT_KANA[tens] + "じゅう")
    if ones:
        parts.append(_DIGIT_KANA[ones])
    return "".join(parts)


def number_to_kana(value: int) -> str:
    if value == 0:
        return "ゼロ"
    parts: list = []
    for unit, size in (("ちょう", 10**12), ("おく", 10**8), ("まん", 10**4)):
        head, value = divmod(value, size)
        if head:
            spelled = _kana_group(head) if head < 10**4 else number_to_kana(head)
            if unit == "ちょう" and spelled.endswith(("いち", "はち")):
                spelled = spelled[:-1] + "っ"  # いっちょう, はっちょう
            parts.append(spelled + unit)
    if value:
        parts.append(_kana_group(value))
    return "".join(parts)


def _fraction_kana(fraction: str) -> str:
    return "".join(_DIGIT_KANA[int(d)] for d in fraction)


# counter -> (reading, {final-digit overrides}); key 10 replaces a trailing
# じゅう (10, 20, 30 ... share the fused form).
_SOKUON = {1: "いっ", 6: "ろっ", 8: "はっ", 10: "じゅっ"}


def _sokuon(base: str, voiced3: Optional[str] = None, p: bool = False) -> Dict[int, str]:
    """Overrides for a counter whose 1/6/8/10 geminate (いっこ, ろっこ ...)."""
    head = ("ぱぴぷぺぽ"["はひふへほ".index(base[0])] + base[1:]) if p else base
    table = {k: v + head for k, v in _SOKUON.items()}
    if voiced3:
        table[3] = "さん" + voiced3
    return table


_COUNTERS: Dict[str, Tuple[str, Dict[int, str]]] = {
    "分間": ("ふんかん", {**_sokuon("ふんかん", "ぷんかん", p=True), 4: "よんぷんかん"}),
    "分": ("ふん", {**_sokuon("ふん", "ぷん", p=True), 4: "よんぷん"}),
    "秒間": ("びょうかん", {}),
    "秒": ("びょう", {}),
    "時間": ("じかん", {4: "よじかん", 7: "しちじかん", 9: "くじかん"}),
    "時": ("じ", {4: "よじ", 7: "しちじ", 9: "くじ"}),
    "円": ("えん", {4: "よえん"}),
    "年間": ("ねんかん", {4: "よねんかん"}),
    "年": ("ねん", {4: "よねん"}),
    "ヶ月": ("かげつ", _sokuon("かげつ")),
    "か月": ("かげつ", _sokuon("かげつ")),
    "カ月": ("かげつ", _sokuon("かげつ")),
    "月": ("がつ", {4: "しがつ", 7: "しちがつ", 9: "くがつ"}),
    "週間": ("しゅうかん", _sokuon("しゅうかん")),
    "人": ("にん", {4: "よにん"}),
    "名": ("めい", {}),
    "件": ("けん", _sokuon("けん")),
    "個": ("こ", _sokuon("こ")),
    "本": ("ほん", _sokuon("ほん", "ぼん", p=True)),
    "杯": ("はい", _sokuon("はい", "ばい", p=True)),
    "匹": ("ひき", _sokuon("ひき", "びき", p=True)),
    "階": ("かい", {**_sokuon("かい"), 3: "さんがい"}),
    "回": ("かい", _sokuon("かい")),
    "歳": ("さい", {1: "いっさい", 8: "はっさい", 10: "じゅっさい"}),
    "冊": ("さつ", {1: "いっさつ", 8: "はっさつ", 10: "じゅっさつ"}),
    "枚": ("まい", {}),
    "台": ("だい", {}),
    "度": ("ど", {}),
    "割": ("わり", {}),
    "倍": ("ばい", {}),
    "位": ("い", {}),
    "番": ("ばん", {}),
    "号": ("ごう", {}),
    "点": ("てん", _sokuon("てん")),
    "パーセント": ("パーセント", _sokuon("パーセント")),
    # Units written in Latin letters after a number.
    "TB": ("テラバイト", {}),
    "GB": ("ギガバイト", {}),
    "MB": ("メガバイト", {}),
    "KB": ("キロバイト", {}),
    "GHz": ("ギガヘルツ", {}),
    "MHz": ("メガヘルツ", {}),
    "kHz": ("キロヘルツ", {}),
    "Hz": ("ヘルツ", {}),
    "ms": ("ミリびょう", {}),
    "km/h": ("キロメートル毎時", {}),
    "km": ("キロメートル", {}),
    "cm": ("センチメートル", {}),
    "mm": ("ミリメートル", {}),
    "m": ("メートル", {}),
    "kg": ("キログラム", {}),
    "mg": ("ミリグラム", {}),
    "ml": ("ミリリットル", {}),
    "mL": ("ミリリットル", {}),
}
_DAY_KANA = {
    1: "ついたち", 2: "ふつか", 3: "みっか", 4: "よっか", 5: "いつか",
    6: "むいか", 7: "なのか", 8: "ようか", 9: "ここのか", 10: "とおか",
    14: "じゅうよっか", 20: "はつか", 24: "にじゅうよっか",
}
_PEOPLE_KANA = {1: "ひとり", 2: "ふたり"}


def _counted(value: int, counter: str, *, date: bool = False) -> str:
    if counter in ("日", "日間"):
        # Day counts share the calendar readings (みっか, みっかかん) except 1,
        # which is ついたち only as a date and いちにち as a span.
        suffix = "かん" if counter == "日間" else ""
        if value in _DAY_KANA and (value != 1 or date):
            return _DAY_KANA[value] + suffix
        return number_to_kana(value) + "にち" + suffix
    if counter == "人" and value in _PEOPLE_KANA:
        return _PEOPLE_KANA[value]
    if counter == "歳" and value == 20:
        return "はたち"
    base, overrides = _COUNTERS.get(counter, (counter, {}))
    kana = number_to_kana(value)
    geminated = overrides.get(1, "")
    if value % 100 == 0 and kana.endswith("ゃく") and geminated.startswith("いっ"):
        # ひゃっぽん, さんびゃっかい, はっぴゃっこ: the hundred geminates too.
        return kana[:-1] + "っ" + geminated[2:]
    if kana.endswith("ん") and 3 in overrides and overrides[3].startswith("さん"):
        # After ん the counter voices as it does after さん: せんぼん, いちまんぷん.
        return kana + overrides[3][2:]
    if value % 10 == 0 and value % 100 != 0 and 10 in overrides:
        return kana[: -len("じゅう")] + overrides[10]
    last = value % 10
    if last and last in overrides and (value % 100 != 0):
        return kana[: -len(_DIGIT_KANA[last])] + overrides[last]
    return kana + base


def _counted_text(number: str, counter: str, *, date: bool = False) -> str:
    number = number.replace(",", "")
    if "." in number:
        integer, fraction = number.split(".", 1)
        base = _COUNTERS.get(counter, ({"日": "にち"}.get(counter, counter), {}))[0]
        return number_to_kana(int(integer)) + "てん" + _fraction_kana(fraction) + base
    return _counted(int(number), counter, date=date)


_COUNTER_ALT = "|".join(
    re.escape(k) for k in sorted([*_COUNTERS, "日", "日間"], key=len, reverse=True)
)
_COMMA_NUMBER = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
# Digits mixed with 兆/億/万 (12万円, 1億2000万, 1.5万人) are folded into one
# integer first, so the counter pass reads じゅうにまんえん rather than leaving
# じゅうに万円 for the model to finish.
_SCALES = {"兆": 10**12, "億": 10**8, "万": 10**4}
_KANJI_SCALED = re.compile(
    r"(?<![A-Za-z0-9.])((?:\d+(?:\.\d+)?[兆億万])+)(\d{1,4})?(?![\d.])"
)


def _unscale(match: "re.Match[str]") -> str:
    # Fractions, not floats: exact for 1.5万 and cannot overflow on a long
    # digit run, which would otherwise raise out of synthesize.
    total = Fraction(0)
    for number, scale in re.findall(r"(\d+(?:\.\d+)?)([兆億万])", match.group(1)):
        if len(number) > 20:
            return match.group(0)
        total += Fraction(number) * _SCALES[scale]
    if match.group(2):
        total += int(match.group(2))
    if total.denominator != 1 or total >= 10**16:
        return match.group(0)
    return str(total.numerator)

_PERCENT = re.compile(r"(?<=\d)\s*%")
_DATE = re.compile(r"(?:(\d{1,4})年)?(\d{1,2})月(\d{1,2})日")
_TIME = re.compile(r"(\d{1,2})時(?!間)(?:(\d{1,2})分(?!間))?(?:(\d{1,2})秒(?!間))?")
_FRACTION = re.compile(r"(\d+)分の(\d+)")
# A hyphen touching digits marks an identifier (GPT-4, a716-4466, x-1): real
# ranges and minus signs were already spelled out by japanese_symbols.
_COUNTED = re.compile(rf"(?<![A-Za-z0-9.\-])(\d+(?:\.\d+)?)\s?({_COUNTER_ALT})(?![A-Za-z])")
_VERSION = re.compile(r"(?<![A-Za-z0-9_.\-])([vV])?(\d+(?:\.\d+){2,})(?![A-Za-z0-9_.\-])")
_DECIMAL = re.compile(r"(?<![A-Za-z0-9._#\-])(\d+)\.(\d+)(?![A-Za-z0-9._%\-])")
_BARE_NUMBER = re.compile(r"(?<![A-Za-z0-9._#\-])(0|[1-9]\d{0,15})(?![A-Za-z0-9._%\-])")


_KANJI_DIGIT = "〇一二三四五六七八九"


def _kanji_group(value: int) -> str:
    out = ""
    for size, mark in ((1000, "千"), (100, "百"), (10, "十")):
        head, value = divmod(value, size)
        if head:
            out += ("" if head == 1 else _KANJI_DIGIT[head]) + mark
    return out + (_KANJI_DIGIT[value] if value else "")


def number_to_kanji(value: int) -> str:
    """123万4567 -> 百二十三万四千五百六十七; 0 -> ゼロ."""
    if value == 0:
        return "ゼロ"
    parts = []
    for mark, size in (("兆", 10**12), ("億", 10**8), ("万", 10**4)):
        head, value = divmod(value, size)
        if head:
            parts.append((_kanji_group(head) if head < 10**4 else number_to_kanji(head)) + mark)
    if value:
        parts.append(_kanji_group(value))
    return "".join(parts)


def _kanji_decimal(integer: str, fraction: str) -> str:
    return number_to_kanji(int(integer)) + "点" + "".join(_KANJI_DIGIT[int(d)] for d in fraction)


def _unit_reading(counter: str) -> str:
    """Latin unit symbols are spelled in katakana; Japanese counters stay."""
    if counter.isascii():
        return _COUNTERS[counter][0]
    return counter


def _kanji_counted(number: str, counter: str, *, date: bool = False) -> str:
    number = number.replace(",", "")
    if counter == "日" and date and number == "1":
        return "ついたち"  # 一日 alone is いちにち as often as ついたち
    if "." in number:
        head = _kanji_decimal(*number.split(".", 1))
    else:
        head = number_to_kanji(int(number))
    return head + _unit_reading(counter)


def _version_kana(m: "re.Match[str]") -> str:
    return ("バージョン" if m.group(1) else "") + "てん".join(
        number_to_kana(int(part)) if i == 0 else _fraction_kana(part)
        for i, part in enumerate(m.group(2).split("."))
    )


def _digits_grouped(value: int) -> str:
    """1234567 -> 123万4567: digits the model reads, scale words it cannot miss."""
    parts = []
    for mark, size in (("兆", 10**12), ("億", 10**8), ("万", 10**4)):
        head, value = divmod(value, size)
        if head:
            parts.append(f"{head}{mark}")
    if value:
        parts.append(str(value))
    return "".join(parts) or "0"


NUMERAL_STYLES = ("kanji", "digits", "kana")


def expand_numbers(text: str, numerals: str = "digits") -> str:
    """Make numbers unambiguous for the model in one of three spellings.

    digits  (default) only what the model misreads is rewritten: grouping
            (123万4567), % and Latin units, versions; 3月5日 stays as
            written, which keeps the phrasing a listener expects.
    kanji   百二十三万四千五百六十七人, 三月五日, 十時三十分: same phrasing,
            and the counter reading is left to the model's kanji knowledge.
    kana    everything in hiragana. Deterministic, but a long kana run loses
            its word boundaries: さんがついつか is phrased さんが・ついつか.

    Digits glued to Latin letters (iPhone15, PR#123, GPT-4) are left alone in
    every style: those are names, and the lexicon is the place to pin them.
    """
    if numerals not in NUMERAL_STYLES:
        raise ValueError(f"unknown numeral style {numerals!r}")
    if numerals == "kana":
        return _expand_kana(text)
    text = text.translate(_FULLWIDTH)
    text = _COMMA_NUMBER.sub("", text)
    text = _KANJI_SCALED.sub(_unscale, text)
    text = _VERSION.sub(_version_kana, text)
    if numerals == "digits":
        text = _PERCENT.sub("パーセント", text)
        text = _COUNTED.sub(
            lambda m: m.group(1) + _unit_reading(m.group(2))
            if m.group(2).isascii()
            else m.group(0),
            text,
        )
        return re.sub(
            r"(?<![A-Za-z0-9._#\-])(\d{5,16})(?![A-Za-z0-9._%\-])",
            lambda m: _digits_grouped(int(m.group(1))),
            text,
        )
    text = _PERCENT.sub("パーセント", text)
    text = _DATE.sub(
        lambda m: (number_to_kanji(int(m.group(1))) + "年" if m.group(1) else "")
        + number_to_kanji(int(m.group(2))) + "月"
        + _kanji_counted(m.group(3), "日", date=True),
        text,
    )
    text = _FRACTION.sub(
        lambda m: number_to_kanji(int(m.group(1))) + "分の" + number_to_kanji(int(m.group(2))),
        text,
    )
    text = _COUNTED.sub(lambda m: _kanji_counted(m.group(1), m.group(2)), text)
    text = _DECIMAL.sub(lambda m: _kanji_decimal(m.group(1), m.group(2)), text)
    return _BARE_NUMBER.sub(lambda m: number_to_kanji(int(m.group(1))), text)


def _expand_kana(text: str) -> str:
    text = text.translate(_FULLWIDTH)
    text = _COMMA_NUMBER.sub("", text)
    text = _KANJI_SCALED.sub(_unscale, text)
    text = _PERCENT.sub("パーセント", text)
    text = _DATE.sub(
        lambda m: (_counted(int(m.group(1)), "年") if m.group(1) else "")
        + _counted(int(m.group(2)), "月")
        + _counted(int(m.group(3)), "日", date=True),
        text,
    )
    text = _TIME.sub(
        lambda m: _counted(int(m.group(1)), "時")
        + (_counted(int(m.group(2)), "分") if m.group(2) else "")
        + (_counted(int(m.group(3)), "秒") if m.group(3) else ""),
        text,
    )
    text = _FRACTION.sub(
        lambda m: number_to_kana(int(m.group(1))) + "ぶんの" + number_to_kana(int(m.group(2))),
        text,
    )
    text = _COUNTED.sub(lambda m: _counted_text(m.group(1), m.group(2)), text)
    text = _VERSION.sub(_version_kana, text)
    text = _DECIMAL.sub(
        lambda m: number_to_kana(int(m.group(1))) + "てん" + _fraction_kana(m.group(2)),
        text,
    )
    text = _BARE_NUMBER.sub(lambda m: number_to_kana(int(m.group(1))), text)
    return text


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def prepare_text(
    text: str,
    *,
    lexicon: Optional[Tuple[Dict[str, str], Optional[re.Pattern]]] = None,
    use_lexicon: bool = True,
    frontend: bool = True,
    numerals: str = "digits",
) -> str:
    """Return the string Irodori should be asked to read.

    The lexicon runs first, on the text as written, so an exact entry
    (RFC-9110, Web3, 3Dプリンタ) is matched before the symbol and number
    passes reinterpret its hyphens and digits.
    """
    if use_lexicon:
        text = apply_lexicon(text, lexicon)
    if frontend:
        text = expand_numbers(japanese_symbols(undo_cleaner_english(text)), numerals)
    return text
