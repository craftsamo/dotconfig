"""Naturalness: stock phrases, translationese, rhythm, lexical and formatting statistics.

Default-lane rules feed the mechanical score; experimental rules run only on
request. Sentence and paragraph rules read prose rows; formatting rules read
every non-code row. Morphology-based rules are unverified without Sudachi.
"""

from collections import Counter
import re
from statistics import mean, pstdev

from .. import catalog
from ..morphology import SegmentTooLarge

MODE = "naturalness"
MORPHOLOGY = True

DEFAULT_LANE = (
    "forbidden_phrase", "translationese", "antithesis_repetition", "low_sentence_variance",
    "english_syntax_inanimate_subject", "nominal_ending", "uniform_paragraph_structure",
    "translationese_morph", "inanimate_subject_morph", "low_burstiness", "repeated_sentence_lead",
    "low_lexical_diversity_ttr", "low_lexical_diversity_mtld", "low_specificity",
)
EXPERIMENTAL_LANE = (
    "high_length_autocorrelation", "paragraph_lead_conjunction", "repeated_syntax_template",
    "english_syntax_cleft_because", "high_bold_density", "high_bullet_ratio", "boilerplate_heading",
    "numbered_phase_structure", "high_emoji_symbol_density",
)
SCORED_RULES = frozenset(DEFAULT_LANE)
EXPERIMENTAL_RULES = frozenset(EXPERIMENTAL_LANE)
MORPH_RULES = frozenset({
    "nominal_ending", "translationese_morph", "inanimate_subject_morph", "low_burstiness",
    "high_length_autocorrelation", "repeated_sentence_lead", "repeated_syntax_template",
    "low_lexical_diversity_ttr", "low_lexical_diversity_mtld", "low_specificity",
})

STRUCTURE_KINDS = ("prose", "heading", "list", "list-continuation", "table")
SYMBOL_POS = ("補助記号", "空白")
CONTENT_POS = ("名詞", "動詞", "形容詞", "副詞")
WINDOW = 10

SENTENCE_VARIANCE_MIN = 5
SENTENCE_VARIANCE_CV = 0.25
NOMINAL_MIN_SENTENCES = 5
PARAGRAPH_CONJ_MIN_PARAGRAPHS = 3
PARAGRAPH_CONJ_RATIO = 0.3
UNIFORM_MIN_PARAGRAPHS = 4
UNIFORM_CV = 0.15
RHYTHM_MIN_SENTENCES = 6
BURSTINESS_BELOW = -0.24
AUTOCORR_MIN_PAIRS = 4
AUTOCORR_ABOVE = 0.6
TEMPLATE_MIN_SENTENCES = 6
TEMPLATE_RATIO = 0.4
LEXICAL_MIN_CHARS = 4000
LEXICAL_MIN_TOKENS = 30
MTLD_MIN_TOKENS = 20
MTLD_FACTOR = 0.72
TTR_BELOW = 0.45
MTLD_BELOW = 40
SPECIFICITY_MIN_CHARS = 80
SPECIFICITY_MIN_WORDS = 15
SPECIFICITY_BELOW = -0.15
BOLD_PER_1000 = 3.0
BOLD_MIN = 3
BULLET_MIN_LINES = 10
BULLET_RATIO = 0.35
PHASE_MIN = 3
EMOJI_PER_1000 = 2.0
EMOJI_MIN = 3
STATS_KEYS = (
    "total_sentences", "nominal_ending_count", "nominal_ending_ratio", "antithesis_hits", "total_paragraphs",
    "paragraph_lead_conjunction_count", "paragraph_lead_conjunction_ratio", "paragraph_sentence_counts",
    "paragraph_sentence_count_cv", "rhythm", "ngram", "lexical_diversity", "structural", "low_specificity",
)
TECH_WORD = re.compile(r"^[A-Za-z][A-Za-z0-9\-_.]*$")


def _cv(values):
    average = mean(values)
    return pstdev(values) / average if average else 0.0


class _Context:
    def __init__(self, inspection):
        self.inspection = inspection
        self.doc = inspection.doc
        self.data = catalog.load("naturalness")
        genres = self.data["genres"]
        self.profile = {**genres["default"], **genres.get(inspection.genre, {})}
        disabled = set(self.profile["disabled_rules"])
        lane = DEFAULT_LANE + (EXPERIMENTAL_LANE if inspection.experimental else ())
        self.active = [rule for rule in lane if rule not in disabled]
        self.sentences = self.doc.sentences()
        self.paragraphs = self.doc.paragraphs()
        self.prose_rows = self.doc.rows_of(("prose",))
        self.tokenized = []
        self.stats = dict.fromkeys(STATS_KEYS)

    def emit(self, rule, severity, line, column, excerpt, reason, related=None):
        if rule in self.active:
            self.inspection.finding(MODE, rule, severity, line, column, excerpt, reason, related)

    def morph_rules(self):
        return [rule for rule in self.active if rule in MORPH_RULES]

    def tokenize(self, line, text, rules):
        """Tokens of ``text``; oversized segments mark ``rules`` unverified at ``line``."""
        try:
            return self.inspection.morph.tokenize(text)
        except SegmentTooLarge:
            for rule in rules:
                self.inspection.unverified(rule, "segment_exceeds_40000_utf8_bytes", line)
            return None


def _window(row, start, end):
    return row.raw[max(0, start - WINDOW):end + WINDOW].strip()


# --- surface patterns -------------------------------------------------------------------------


def _forbidden_phrase(ctx):
    for row in ctx.prose_rows:
        text = row.visible
        for entry in ctx.data["forbidden_phrases"]:
            phrase = entry["phrase"]
            start = text.find(phrase)
            if start < 0:
                continue
            note = "日常の文章でもよく使う語なので、頻度と文脈で判断する。" if entry["weak"] else ""
            reason = f"定型句「{phrase}」がある。{note}この文脈で要る言葉か確認する (expression.md {entry['anchor']})"
            severity = "info" if entry["weak"] else "warn"
            excerpt = _window(row, start, start + len(phrase))
            ctx.emit("forbidden_phrase", severity, row.line, start + 1, excerpt, reason)


def _translationese(ctx):
    patterns = [re.compile(p) for p in ctx.data["translationese_patterns"]]
    for row in ctx.prose_rows:
        text = row.visible
        for pattern in patterns:
            for match in pattern.finditer(text):
                reason = f"翻訳調の型「{match[0]}」がある。短く言い切る形にできないか確認する (expression.md X3)"
                ctx.emit("translationese", "info", row.line, match.start() + 1,
                         _window(row, match.start(), match.end()), reason)


def _antithesis_repetition(ctx):
    patterns = [re.compile(p) for p in ctx.data["antithesis_patterns"]]
    hits = []
    for row in ctx.prose_rows:
        for pattern in patterns:
            hits.extend((row, match.start(), match.end()) for match in pattern.finditer(row.visible))
    count = len(hits)
    ratio = count / len(ctx.sentences) if ctx.sentences else 0.0
    ctx.stats["antithesis_hits"] = count
    if count < ctx.data["antithesis_min_hits"]:
        return
    if ratio < ctx.data["antithesis_info_below"]:
        severity = "info"
    elif ratio >= ctx.profile["antithesis_rate_critical_above"]:
        severity = "critical"
    else:
        severity = "warn"
    related = [row.line for row, _, _ in hits]
    reason = (f"否定→肯定の対比が {count} 回 (全文の {ratio:.1%}) ある。"
              "言い換えの癖になっていないか確認する (expression.md X6)")
    for row, start, end in hits:
        excerpt = row.raw[start:end].strip()
        ctx.emit("antithesis_repetition", severity, row.line, start + 1, excerpt, reason, related)


def _low_sentence_variance(ctx):
    lengths = [len(sentence.text) for sentence in ctx.sentences]
    if len(lengths) < SENTENCE_VARIANCE_MIN or not mean(lengths):
        return
    cv = _cv(lengths)
    if cv < SENTENCE_VARIANCE_CV:
        excerpt = f"文数={len(lengths)} 平均{mean(lengths):.1f}字 CV={cv:.3f}"
        reason = "文の長さがそろいすぎている。長短の差で読みのリズムを作れるか確認する (expression.md X7)"
        ctx.emit("low_sentence_variance", "warn", ctx.sentences[0].line, 1, excerpt, reason)


def _english_syntax(ctx):
    patterns = [re.compile(p) for p in ctx.data["inanimate_subject_patterns"]]
    reason = "抽象的な主語が「示す」「もたらす」などを受けている。人や行為を主語にできないか確認する (expression.md X4)"
    for row in ctx.prose_rows:
        for pattern in patterns:
            for match in pattern.finditer(row.visible):
                ctx.emit("english_syntax_inanimate_subject", "info", row.line, match.start() + 1,
                         row.raw[match.start():match.end()].strip(), reason)
    head = re.compile(ctx.data["cleft_head"])
    follow = re.compile(ctx.data["cleft_follow"])
    reason = "「それは〜である。なぜなら〜」と結論を先に置く型がある。理由と結論を一文でつなげないか確認する (expression.md X3)"
    for first, second in zip(ctx.sentences, ctx.sentences[1:]):
        if head.match(first.text) and follow.match(second.text):
            ctx.emit("english_syntax_cleft_because", "warn", first.line, first.start + 1,
                     f"{first.raw}。{second.raw}", reason)


def _paragraph_rules(ctx):
    paragraphs = ctx.paragraphs
    conjunctions = ctx.data["paragraph_conjunctions"]
    matched = []
    for rows in paragraphs:
        lead = rows[0].visible.strip()
        conj = next((c for c in conjunctions if lead.startswith(c)), None)
        if conj:
            matched.append((rows[0], conj))
    ratio = len(matched) / len(paragraphs) if paragraphs else 0.0
    ctx.stats.update(total_paragraphs=len(paragraphs), paragraph_lead_conjunction_count=len(matched),
                     paragraph_lead_conjunction_ratio=round(ratio, 4))
    if len(paragraphs) >= PARAGRAPH_CONJ_MIN_PARAGRAPHS and ratio >= PARAGRAPH_CONJ_RATIO:
        related = [row.line for row, _ in matched]
        for row, conj in matched:
            reason = (f"段落が「{conj}」で始まる (段落頭の接続詞は {ratio:.0%})。"
                      "前段落とのつながりで足りないか確認する (readability.md H3)")
            ctx.emit("paragraph_lead_conjunction", "info", row.line, 1, row.raw.strip()[:40], reason, related)

    per_row = Counter(sentence.row.line for sentence in ctx.sentences)
    counts = [sum(per_row[row.line] for row in rows) for rows in paragraphs]
    cv = _cv(counts) if len(counts) >= UNIFORM_MIN_PARAGRAPHS else None
    ctx.stats.update(paragraph_sentence_counts=counts,
                     paragraph_sentence_count_cv=round(cv, 4) if cv is not None else None)
    if cv is not None and cv < UNIFORM_CV:
        excerpt = f"段落数={len(counts)} 文数={counts}"
        reason = "どの段落もほぼ同じ文数になっている。内容の重さに合わせて段落を伸縮できるか確認する (expression.md X7)"
        ctx.emit("uniform_paragraph_structure", "info", 1, 1, excerpt, reason)


# --- morphology -------------------------------------------------------------------------------


def _strip_trailing_symbols(tokens):
    end = len(tokens)
    while end and tokens[end - 1].pos[0] in SYMBOL_POS:
        end -= 1
    return tokens[:end]


def _strip_leading_symbols(tokens):
    start = 0
    while start < len(tokens) and tokens[start].pos[0] in SYMBOL_POS:
        start += 1
    return tokens[start:]


def _nominal_ending(ctx):
    pairs = ctx.tokenized
    count = 0
    for _, tokens in pairs:
        content = _strip_trailing_symbols(tokens)
        count += bool(content) and content[-1].pos[0] == "名詞"
    total = len(pairs)
    chars = sum(len(sentence.raw) for sentence, _ in pairs)
    ratio = round(count / total, 4) if total else 0.0
    ctx.stats.update(nominal_ending_count=count, nominal_ending_ratio=ratio)
    if total >= NOMINAL_MIN_SENTENCES and chars >= ctx.profile["nominal_min_chars"] and count == 0:
        line = pairs[-1][0].line
        reason = "体言止めが一つもなく、文末が単調になりやすい。言い切りの変化を入れられるか確認する (expression.md X7)"
        ctx.emit("nominal_ending", "info", line, 1, f"体言止め0件（{total}文、約{chars}字）", reason)


def _translationese_morph(ctx):
    reason = "「〜することができる」型がある。「〜できる」と短くできないか確認する (expression.md X3)"
    for sentence, tokens in ctx.tokenized:
        for i in range(len(tokens) - 2):
            first, particle, verb = tokens[i:i + 3]
            if (first.surface == "こと" and first.pos[0] == "名詞"
                    and particle.pos[0] == "助詞" and particle.surface in ("が", "は")
                    and verb.pos[0] == "動詞" and verb.surface.startswith("でき")):
                start = tokens[max(0, i - 4)].begin
                ctx.emit("translationese_morph", "info", sentence.line, sentence.start + start + 1,
                         sentence.raw[start:verb.end], reason)


def _subject_end(tokens, i, data):
    token = tokens[i]
    if token.surface in data["abstract_pronouns"]:
        return i
    if token.pos[0] == "名詞" and token.surface in data["abstract_subject_nouns"]:
        return i
    if i + 1 < len(tokens) and token.surface + tokens[i + 1].surface in data["abstract_subject_pairs"]:
        return i + 1
    return None


def _smell_verb(tokens, k, verbs):
    """Return (lemma, last index) when a predicate starting at ``k`` is a listed verb.

    Split mode C cuts 意味する or 浮き彫りにする into noun (+ に) + する, so those
    shapes are rebuilt before the lookup.
    """
    token = tokens[k]
    if token.pos[0] == "動詞" and token.dictionary_form in verbs:
        return token.dictionary_form, k
    if token.pos[0] != "名詞":
        return None
    for tail, length in ((("する",), 1), (("に", "する"), 2)):
        following = tokens[k + 1:k + 1 + length]
        if len(following) == length and [t.dictionary_form for t in following] == list(tail) \
                and following[-1].pos[0] == "動詞":
            lemma = token.dictionary_form + "".join(tail)
            if lemma in verbs:
                return lemma, k + length
    return None


def _inanimate_subject_morph(ctx):
    data = ctx.data
    verbs = set(data["transitive_smell_verbs"])
    for sentence, tokens in ctx.tokenized:
        skip_until = -1
        for i in range(len(tokens)):
            if i <= skip_until:
                continue
            end = _subject_end(tokens, i, data)
            if end is None:
                continue
            skip_until = max(skip_until, end)
            j = end + 1
            if j >= len(tokens) or tokens[j].pos[0] != "助詞" or tokens[j].surface not in ("が", "は"):
                continue
            for k in range(j + 1, len(tokens)):
                hit = _smell_verb(tokens, k, verbs)
                if hit:
                    subject = "".join(t.surface for t in tokens[i:end + 1])
                    start = tokens[max(0, i - 3)].begin
                    reason = (f"抽象主語「{subject}」が「{hit[0]}」を受けている。"
                              "人や行為を主語にできないか確認する (expression.md X4)")
                    ctx.emit("inanimate_subject_morph", "info", sentence.line, sentence.start + start + 1,
                             sentence.raw[start:tokens[hit[1]].end], reason)
                    break


def _mora_length(tokens, small):
    total = 0
    for token in tokens:
        reading = token.reading_form or token.surface
        total += sum(1 for k, char in enumerate(reading) if k == 0 or char not in small)
    return total


def _rhythm(ctx):
    pairs = ctx.tokenized
    if len(pairs) < RHYTHM_MIN_SENTENCES:
        ctx.stats["rhythm"] = {}
        return
    lengths = [_mora_length(tokens, ctx.data["small_kana"]) for _, tokens in pairs]
    average, spread = mean(lengths), pstdev(lengths)
    burstiness = (spread - average) / (spread + average) if spread + average else 0.0
    xs, ys = lengths[:-1], lengths[1:]
    autocorr = None
    if len(xs) >= AUTOCORR_MIN_PAIRS and pstdev(xs) > 0 and pstdev(ys) > 0:
        mx, my = mean(xs), mean(ys)
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / len(xs)
        autocorr = cov / (pstdev(xs) * pstdev(ys))
    ctx.stats["rhythm"] = {
        "mora_mean": round(average, 3), "mora_stdev": round(spread, 3), "burstiness": round(burstiness, 4),
        "length_autocorrelation_lag1": round(autocorr, 4) if autocorr is not None else None,
    }
    line = pairs[0][0].line
    if burstiness < BURSTINESS_BELOW:
        excerpt = f"burstiness={burstiness:.3f} 平均{average:.1f}拍 SD={spread:.1f}"
        reason = "文の長短の差が小さく、リズムが平板になっている。短い文や長い文を混ぜられるか確認する (expression.md X7)"
        ctx.emit("low_burstiness", "warn", line, 1, excerpt, reason)
    if autocorr is not None and autocorr > AUTOCORR_ABOVE:
        reason = "隣り合う文の長さが連動している。同じ長さの型が続いていないか確認する (expression.md X7)"
        ctx.emit("high_length_autocorrelation", "info", line, 1, f"lag-1 自己相関={autocorr:.3f}", reason)


def _is_tech_lead(token):
    return token.pos[:2] == ("名詞", "固有名詞") or bool(TECH_WORD.match(token.surface))


def _sentence_leads(ctx):
    leads = [(sentence, _strip_leading_symbols(tokens)) for sentence, tokens in ctx.tokenized]
    threshold = ctx.profile["lead_repeat_threshold"]
    groups = {}
    for sentence, tokens in leads:
        if len(tokens) >= 2:
            groups.setdefault(tokens[0].surface + tokens[1].surface, []).append((sentence, tokens[0]))
    for key, members in groups.items():
        if len(members) < threshold:
            continue
        related = [sentence.line for sentence, _ in members]
        tech = _is_tech_lead(members[0][1])
        note = "固有名詞や技術用語なら問題ない。" if tech else "意図した反復なら残す。"
        reason = f"文頭「{key}」が {len(members)} 回続く。{note}書き出しを変えられるか確認する (readability.md H1)"
        for sentence, _ in members:
            ctx.emit("repeated_sentence_lead", "info", sentence.line, sentence.start + 1, sentence.raw[:20],
                     reason, related)

    grams = [(sentence, tuple(t.pos[0] for t in tokens[:4]))
             for sentence, tokens in leads if len(tokens) >= 4]
    ctx.stats["ngram"] = {"lead_pos_4gram_top": None, "lead_pos_4gram_ratio": None}
    if len(grams) < TEMPLATE_MIN_SENTENCES:
        return
    counts = Counter(gram for _, gram in grams)
    top = max(counts, key=lambda gram: counts[gram])
    ratio = counts[top] / len(grams)
    ctx.stats["ngram"] = {"lead_pos_4gram_top": "/".join(top), "lead_pos_4gram_ratio": round(ratio, 4)}
    if ratio < TEMPLATE_RATIO:
        return
    members = [sentence for sentence, gram in grams if gram == top]
    related = [sentence.line for sentence in members]
    reason = (f"文頭の品詞の並び「{'/'.join(top)}」が {ratio:.0%} の文で共通する。"
              "構文の型を使い回していないか確認する (expression.md X7)")
    for sentence in members:
        ctx.emit("repeated_syntax_template", "info", sentence.line, sentence.start + 1, sentence.raw[:20],
                 reason, related)


def _mtld_pass(sequence):
    factors, types, count = 0.0, set(), 0
    for token in sequence:
        types.add(token)
        count += 1
        if len(types) / count <= MTLD_FACTOR:
            factors += 1
            types, count = set(), 0
    if count:
        ratio = len(types) / count
        factors += min((1 - ratio) / (1 - MTLD_FACTOR) if ratio < 1 else 0, 1)
    return len(sequence) / factors if factors > 0 else len(sequence)


def _mtld(sequence):
    if len(sequence) < MTLD_MIN_TOKENS:
        return None
    return (_mtld_pass(sequence) + _mtld_pass(sequence[::-1])) / 2


def _lexical_diversity(ctx):
    words = [t.dictionary_form for _, tokens in ctx.tokenized for t in tokens if t.pos[0] in CONTENT_POS]
    chars = sum(len(sentence.raw) for sentence, _ in ctx.tokenized)
    stats = {"ttr": None, "mtld": None, "content_token_count": len(words), "doc_char_count": chars,
             "skipped_too_short": chars < LEXICAL_MIN_CHARS}
    ctx.stats["lexical_diversity"] = stats
    if stats["skipped_too_short"] or len(words) < LEXICAL_MIN_TOKENS:
        return
    ttr = len(set(words)) / len(words)
    mtld = _mtld(words)
    stats.update(ttr=round(ttr, 4), mtld=round(mtld, 2) if mtld is not None else None)
    line = ctx.tokenized[0][0].line
    if ttr < TTR_BELOW:
        reason = "内容語の種類が少なく、同じ語が繰り返されている。言い換えか削除で足りるか確認する (expression.md X8)"
        ctx.emit("low_lexical_diversity_ttr", "info", line, 1,
                 f"TTR={ttr:.3f}（内容語{len(words)}語中{len(set(words))}種）", reason)
    if mtld is not None and mtld < MTLD_BELOW:
        reason = "文書の長さを考えても語彙の幅が狭い。同じ語の使い回しがないか確認する (expression.md X8)"
        ctx.emit("low_lexical_diversity_mtld", "info", line, 1, f"MTLD={mtld:.1f}", reason)


def _specificity_words(ctx, rows):
    words = []
    for row in rows:
        if not row.visible.strip():
            continue
        tokens = ctx.tokenize(row.line, row.visible, ["low_specificity"])
        if tokens is None:
            return None
        words.extend(t for t in tokens if t.pos[0] in CONTENT_POS)
    return words


def _low_specificity(ctx):
    data = ctx.data
    abstract = set(data["abstract_nouns"])
    numeric = re.compile(data["numeric_quantity"])
    evaluated = fired = 0
    for rows in ctx.paragraphs:
        text = "\n".join(row.visible for row in rows)
        if len(text) < SPECIFICITY_MIN_CHARS:
            continue
        words = _specificity_words(ctx, rows)
        if words is None or len(words) < SPECIFICITY_MIN_WORDS:
            continue
        evaluated += 1
        n = len(words)
        proper = sum(1 for t in words if t.pos[:2] == ("名詞", "固有名詞")) / n
        vague = sum(1 for t in words if t.pos[0] == "名詞" and t.dictionary_form in abstract) / n
        numbers = len(numeric.findall(text)) / n
        example = any(marker in text for marker in data["example_markers"])
        score = proper + numbers + (0.1 if example else 0.0) - vague * 1.5
        if score < SPECIFICITY_BELOW:
            fired += 1
            reason = (f"固有名詞・数値・実例が乏しい段落がある (具体性 {score:.2f}、抽象名詞率 {vague:.2f})。"
                      "文体より材料の不足を疑う (expression.md X9)")
            ctx.emit("low_specificity", "info", rows[0].line, 1, rows[0].raw.strip()[:40], reason)
    ctx.stats["low_specificity"] = {"paragraphs_evaluated": evaluated, "paragraphs_fired": fired}


# --- formatting -------------------------------------------------------------------------------


def _first_line(hits):
    return hits[0][0].line if hits else 1


def _matches(rows, pattern):
    return [(row, match) for row in rows for match in pattern.finditer(row.visible)]


def _structural(ctx):
    data = ctx.data
    rows = ctx.doc.rows_of(STRUCTURE_KINDS)
    total_chars = len(ctx.doc.text) or 1
    bold = _matches(rows, re.compile(data["bold_span"]))
    phases = _matches(rows, re.compile(data["numbered_phase"]))
    emoji = _matches(rows, re.compile(data["emoji_symbol"]))
    non_blank = [row for row in rows if row.raw.strip()]
    bullets = [row for row in non_blank if row.kind == "list"]
    headings = []
    for row in rows:
        title = row.visible.strip().lower() if row.kind == "heading" else ""
        word = next((w for w in data["boilerplate_heading_words"] if title.startswith(w)), None)
        if word:
            headings.append((row, word))
    bold_rate = len(bold) / total_chars * 1000
    emoji_rate = len(emoji) / total_chars * 1000
    ctx.stats["structural"] = {
        "bold_span_count": len(bold), "bold_per_1000_chars": round(bold_rate, 3),
        "bullet_line_count": len(bullets), "non_blank_line_count": len(non_blank),
        "boilerplate_heading_count": len(headings), "numbered_phase_hit_count": len(phases),
        "emoji_symbol_count": len(emoji), "emoji_symbol_per_1000_chars": round(emoji_rate, 3),
    }
    if bold_rate >= BOLD_PER_1000 and len(bold) >= BOLD_MIN:
        reason = "太字が多く、強調が効かなくなっている。本当に目立たせる語に絞れるか確認する (expression.md X10)"
        ctx.emit("high_bold_density", "info", _first_line(bold), bold[0][1].start() + 1,
                 f"太字{len(bold)}箇所（1000字あたり{bold_rate:.2f}）", reason)
    ratio = len(bullets) / len(non_blank) if non_blank else 0.0
    if len(non_blank) >= BULLET_MIN_LINES and ratio >= BULLET_RATIO:
        related = [row.line for row in bullets] if len(bullets) > 1 else None
        reason = "箇条書きの行が多く、論理のつながりが省かれやすい。文章でつなぐべき箇所がないか確認する (expression.md X10)"
        ctx.emit("high_bullet_ratio", "info", bullets[0].line if bullets else 1, 1,
                 f"箇条書き{len(bullets)}/{len(non_blank)}行（{ratio:.0%}）", reason, related)
    for row, word in headings:
        reason = f"「{word}」で始まる定型見出しがある。中身を表す見出しにできないか確認する (expression.md X10)"
        ctx.emit("boilerplate_heading", "info", row.line, row.content_start + 1, row.raw.strip()[:40], reason)
    if len(phases) >= PHASE_MIN:
        reason = "「フェーズ 1」型の段階番号が続く。番号でなく内容で区切れるか確認する (expression.md X10)"
        ctx.emit("numbered_phase_structure", "info", _first_line(phases), phases[0][1].start() + 1,
                 f"段階番号{len(phases)}回", reason)
    if emoji_rate >= EMOJI_PER_1000 and len(emoji) >= EMOJI_MIN:
        reason = "絵文字や装飾記号が多い。言葉だけで伝わらないか確認する (expression.md X10)"
        ctx.emit("high_emoji_symbol_density", "info", _first_line(emoji), emoji[0][1].start() + 1,
                 f"絵文字・記号{len(emoji)}箇所（1000字あたり{emoji_rate:.2f}）", reason)


# --- entry ------------------------------------------------------------------------------------


def _tokenize_sentences(ctx):
    rules = ctx.morph_rules()
    for sentence in ctx.sentences:
        tokens = ctx.tokenize(sentence.line, sentence.text, rules)
        if tokens is not None:
            ctx.tokenized.append((sentence, tokens))


def run(inspection):
    ctx = _Context(inspection)
    inspection.executed(*[rule for rule in ctx.active if rule not in MORPH_RULES])
    morph_rules = ctx.morph_rules()
    morph_ok = inspection.needs_morphology(*morph_rules) if morph_rules else inspection.morph.available
    ctx.stats["total_sentences"] = len(ctx.sentences)
    _structural(ctx)
    _forbidden_phrase(ctx)
    _translationese(ctx)
    _antithesis_repetition(ctx)
    _low_sentence_variance(ctx)
    _english_syntax(ctx)
    _paragraph_rules(ctx)
    if morph_ok:
        _tokenize_sentences(ctx)
        _nominal_ending(ctx)
        _translationese_morph(ctx)
        _inanimate_subject_morph(ctx)
        _rhythm(ctx)
        _sentence_leads(ctx)
        _lexical_diversity(ctx)
        _low_specificity(ctx)
    inspection.stats(MODE, ctx.stats)
