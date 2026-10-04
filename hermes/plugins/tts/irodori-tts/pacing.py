"""Pacing side of the Irodori-TTS provider: how long each request may run.

Irodori fills whatever duration it is given. Its duration predictor is
speaker-conditioned, and with some reference voices it puts a floor of about
3.5 s under every utterance: a 7-mora "もう終わったの？" is allotted 3.4 s where
another voice gets 1.5 s. The model then fills the slack with speech nobody
wrote -- the sentence again, or fragments before or after it -- loud enough
that no level gate can remove it. Long text is predicted correctly with every
voice; the floor only bites below about 20 morae, which is a short reply or
the short last sentence the server's own chunker leaves behind.

So the provider splits the text itself and caps each request's duration with
an estimate made from the text. The cap is a ceiling, not a target: where the
predictor allots less, its value stands. The constants were measured on the
lethe reference against kana-whisper: at 7.5 morae/s the extra speech went
from 43 of 75 short renders to 1, and at 6.5 morae/s 17 of 75 kept it, so the
slack the model tolerates is a few hundred milliseconds at most.

Chunks are whole sentences. The server's chunker also cuts at a comma once 80
characters have accumulated, and each chunk is spoken as a complete utterance,
so a mid-sentence cut ends on a falling sentence-final contour.

Kept free of numpy and of Hermes imports, like ``reading``, so the reading
checker can load it on its own.
"""

from __future__ import annotations

import re
from typing import Dict, List

# A chunk is closed at the first sentence end after this many characters, the
# same threshold the server's chunker uses by default.
CHUNK_CHARS = 80
# A last chunk shorter than this is merged into the one before it rather than
# rendered on its own ("…です。よろしくお願いします。").
TAIL_CHARS = 40
# A single sentence longer than this is cut at commas instead.
LONG_SENTENCE_CHARS = 2 * CHUNK_CHARS

MORA_PER_SECOND = 7.5
COMMA_SECONDS = 0.25
STOP_SECONDS = 0.35
BASE_SECONDS = 0.3
# An emoji is performed as a laugh, sob or hum; one measured +1.48 s.
EMOJI_SECONDS = 1.5

# A sentence ends at Japanese or ASCII stops, plus any closing bracket. An
# ASCII or full-width period counts only when it is not a decimal point
# (3.5, v2.10.1) or part of an ellipsis.
_SENTENCE = re.compile(
    r".*?(?:(?:[。！？!?]|(?<![.\d])[.．](?![.\d]))+[」』）)】]*|…+(?=\s|$)|$)", re.S
)
_COMMA = re.compile(r".*?(?:[、，,]|$)", re.S)
_SMALL_KANA = frozenset("ゃゅょぁぃぅぇぉゎャュョァィゥェォヮ")
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]"
    "(?:[\uFE0F\U0001F3FB-\U0001F3FF]|\u200D[\U0001F000-\U0001FAFF\u2600-\u27BF])*"
)


def _pieces(pattern: "re.Pattern[str]", text: str) -> List[str]:
    return [piece for piece in pattern.findall(text) if piece.strip()]


def _sentences(text: str) -> List[str]:
    out: List[str] = []
    for sentence in _pieces(_SENTENCE, text):
        if len(sentence) <= LONG_SENTENCE_CHARS:
            out.append(sentence)
            continue
        # A run-on sentence: cut at commas, and a clause with none is cut by
        # length, because the model's text encoder truncates what it cannot
        # hold and a dropped clause is worse than a pause inside one.
        part = ""
        for clause in _pieces(_COMMA, sentence):
            while len(clause) > LONG_SENTENCE_CHARS:
                out.append(part + clause[:LONG_SENTENCE_CHARS])
                part, clause = "", clause[LONG_SENTENCE_CHARS:]
            part += clause
            if len(part) >= CHUNK_CHARS:
                out.append(part)
                part = ""
        if part:
            out.append(part)
    return out


def split_for_speech(text: str) -> List[str]:
    """Sentence-aligned chunks of CHUNK_CHARS or more, no short tail, none
    much longer than LONG_SENTENCE_CHARS. Joined back they are the text, less
    the whitespace at the cuts."""
    chunks: List[str] = []
    current = ""
    for sentence in _sentences(text):
        if current.strip() and len(current) + len(sentence) > LONG_SENTENCE_CHARS:
            chunks.append(current.strip())
            current = ""
        current += sentence
        if len(current.strip()) >= CHUNK_CHARS:
            chunks.append(current.strip())
            current = ""
    tail = current.strip()
    if tail:
        if chunks and len(tail) < TAIL_CHARS and len(chunks[-1]) + len(tail) <= LONG_SENTENCE_CHARS:
            chunks[-1] = chunks[-1] + tail
        else:
            chunks.append(tail)
    return chunks or [text.strip()]


def estimate_morae(text: str) -> float:
    """Rough spoken length in morae, from script alone.

    Kana count one each (small kana none), kanji about two, a capital letter
    is spelled (エー, エス) and a lower-case one is part of a word. Checked
    against the corpus readings it lands within two morae on short sentences.
    """
    morae = 0.0
    for ch in _EMOJI.sub("", text):
        if ch in _SMALL_KANA:
            continue
        if "\u3040" <= ch <= "\u30ff":
            morae += 1.0
        elif "\u3400" <= ch <= "\u9fff" or ch == "々":
            morae += 1.9
        elif ch.isascii() and ch.isupper():
            morae += 2.0
        elif ch.isascii() and ch.isalpha():
            morae += 0.8
        elif ch.isdigit():
            # Under the default numeral style digits reach the model as
            # written; read out they run 2-4.5 morae each (25 にじゅうご,
            # 9999 きゅうせんきゅうひゃく…). Over rather than under: a cap
            # that is too short rushes real words.
            morae += 3.5
    return morae


def request_options(text: str, *, caption: bool) -> Dict[str, object]:
    """Server options for one chunk the provider has already split.

    Server chunking is off, since it could still cut the chunk at a comma. A
    caption lifts the cap: direction such as "ゆっくり" may slow the take on
    purpose, and an estimate from the text alone would clip it.
    """
    options: Dict[str, object] = {"chunking_enabled": False}
    if not caption:
        options["max_seconds"] = max_seconds(text)
    return options


def max_seconds(text: str) -> float:
    """The longest a chunk may run before the model starts inventing speech."""
    stops = len(re.findall(r"[。！？!?…]+", text))
    commas = len(re.findall(r"[、，,]", text))
    return round(
        estimate_morae(text) / MORA_PER_SECOND
        + COMMA_SECONDS * commas
        + STOP_SECONDS * max(0, stops - 1)
        + EMOJI_SECONDS * len(_EMOJI.findall(text))
        + BASE_SECONDS,
        2,
    )
