---
name: japanese-writing
description: Use when writing Japanese-language deliverable text — documentation, README, code comments, commit messages, PR titles/bodies, UI copy, error messages, release notes (日本語で書いて, 日本語ドキュメント, 日本語のREADME, 和訳, 日本語化, 表記ゆれ, 文体, 敬体, カタカナ表記, 全角半角, 一文一行, 改行位置, 助詞の省略, 複合名詞, 日本語ライティング). Covers mixed Japanese-English typography (spacing, punctuation), terminology choice (English vs katakana vs code-literal), compound-noun vs particle forms (改行位置 vs 改行の位置), notation consistency (long vowels, kana usage), source line-breaking (one sentence per line), and per-deliverable style. Do NOT use for chat replies (the LanguagePolicy already governs response language) or for i18n/translation-file workflows.
---

<Goal>

Keep Japanese deliverable text consistent: one notation, one terminology
decision rule, one style per deliverable type. These rules eliminate the usual
drift (「Gitの履歴」 vs 「Git の履歴」, サーバ vs サーバー, です・ます混在)
across sessions.

</Goal>

<WhenToApply>

Applies to text that will persist as an artifact written in Japanese:
documentation, README, code comments, commit messages, PR titles and bodies,
UI copy, error messages, release notes, issue text.

Does NOT apply to conversational chat replies — those follow the global
LanguagePolicy, not this skill. Does NOT cover translation-file / i18n
tooling workflows.

</WhenToApply>

<ProjectFirst>

The repository's own convention always wins over this skill:

1. A textlint config (`.textlintrc*`) or prose linter in the repo — obey it,
   and run it for verification.
2. An explicit style guide (`CONTRIBUTING.md`, `docs/style*`).
3. The dominant pattern in the repo's existing Japanese documents.

Only when none of these decide a point, fall back to the rules below.

</ProjectFirst>

<MixedScript>

Rules for 和欧混植 (mixing Japanese with Latin script and digits):

- Put a half-width space between Japanese text and a Latin word or number:
  「Git の履歴」「3 個のファイル」「TypeScript で書く」.
- No space between Japanese text and full-width punctuation, or inside
  brackets adjacent to the quoted term: 「（GitHub）」 not 「（ GitHub ）」.
- Punctuation in Japanese sentences is full-width 「、」「。」. Do not use
  half-width `,` `.` in Japanese prose.
- Parentheses around Latin-only content inside a Japanese sentence may be
  half-width `()`; parentheses containing Japanese are full-width （）.
- Numbers and units are half-width: 「100 ms」「8 GB」. Half-width `%` and
  half-width digits: 「50%」.
- Question/exclamation marks in prose: prefer 「。」; when unavoidable use
  full-width 「？」「！」 followed by no extra space.
- Code identifiers, commands, file paths, and flag names go in backticks and
  stay verbatim; the backticked token counts as a Latin word for spacing:
  「`git rebase` を実行する」.

</MixedScript>

<Terminology>

Decision tree for a technical term in Japanese prose:

1. Code identifier / command / API name / file name → verbatim in backticks:
   `repository`, `git push`, `package.json`. Never translate or katakana-ize.
2. Proper noun (product, service, language) → official original spelling:
   GitHub, TypeScript, Docker, Visual Studio Code. Never 「ギットハブ」.
3. Common technical term in running text → established katakana if one
   exists; otherwise keep the English word (lowercase unless a proper noun).

Reference table for frequent terms (established katakana):

| English | 地の文での表記 |
| --- | --- |
| repository | リポジトリ |
| server | サーバー |
| user | ユーザー |
| directory | ディレクトリ |
| library | ライブラリ |
| release | リリース |
| build | ビルド |
| test | テスト |
| deploy | デプロイ |
| merge | マージ |
| review | レビュー |
| branch | ブランチ |
| interface | インターフェース |
| parameter | パラメーター |
| error | エラー |
| log | ログ |

Kept in English (katakana not established or ambiguous): commit hash,
issue, pull request（または PR）, lint, diff, stash.

Do not mix forms for the same concept within one document. First occurrence
of a less-known term may carry the original in parentheses:
「べき等性（idempotency）」.

</Terminology>

<CompoundNouns>

Particle omission (「改行位置」 vs 「改行の位置」): whether to fuse nouns
into a compound is decided by two TESTS plus a placement rule — never by a
vocabulary list, because the same surface form can be both an established
term and an ad-hoc compression (「改行コード」 = newline character, or a
compression of 「改行されたコード」).

Test 1 — expansion (is it an established term?):
Re-insert 「の」 or the underlying verb and check whether the meaning is
preserved.

- Meaning preserved → ad-hoc compound. In running text, use the expanded
  form: 「変更の内容を確認します」 not 「変更内容を確認します」,
  「エラーの原因」 not 「エラー原因」.
- Meaning changes or breaks → established term. Keep it fused everywhere:
  「改行コード」(\n) ≠ 「改行のコード」, 「環境変数」 ≠ 「環境の変数」 —
  these stay fused even in prose.

Test 2 — collision (is compression forbidden?):
If compressing an ad-hoc phrase would produce the same surface form as an
established term, do NOT compress; keep the verb/particle form.

- 「改行されたコード」 → never compress to 「改行コード」 (misread as \n).
- 「テストされた環境」 → never compress to 「テスト環境」 (misread as the
  staging/test environment). Applies even in headings and labels.

Placement rule (for ad-hoc compounds that pass Test 2):

- Running text and UI explanatory sentences → expanded form with particles:
  「変更の内容」「日本語のドキュメント」「削除の対象」.
- Headings, list-item labels, table headers, UI labels, commit subjects →
  compressed form is acceptable: 「変更内容」「削除対象」 (pairs well with
  体言止め).
- Ad-hoc chains of 3+ nouns are forbidden in running text; unfold them:
  「日本語ドキュメント改行規則」 → 「日本語ドキュメントにおける改行の規則」.

The examples above illustrate the tests; they are not a whitelist.

</CompoundNouns>

<NotationConsistency>

- Long vowel mark: WITH trailing 「ー」 — サーバー, ユーザー, パラメーター,
  コンピューター (JIS Z 8301:2019 / current Microsoft style). Not サーバ.
- Prefer kana over kanji for formal/auxiliary words:
  ください（× 下さい）, できる（× 出来る）, 〜のとおり（× 〜の通り）,
  〜すること（× 〜する事）, ほかに（× 他に）, 〜してみる（× 〜して見る）,
  および（× 及び）, ため（× 為）.
- 送り仮名 follows 本則: 「行う」「表す」「変わる」.
- Choose one of 「〜化」「〜的」 constructions vs plain phrasing and stay
  consistent; avoid stacking （「最適化的な」→「最適化に近い」）.

</NotationConsistency>

<SourceFormatting>

Line-breaking rules for Japanese Markdown / plain-text SOURCE (how the file
is wrapped, independent of prose style):

- One sentence per line: break after every 「。」. Do not hard-wrap Japanese
  prose at a fixed column — a mid-sentence newline renders as a stray
  half-width space on GitHub, and fixed-width wrapping makes diffs span whole
  paragraphs. Sentence-per-line keeps diffs one-sentence-sized and puts the
  rendered space only at sentence boundaries.
- A very long sentence (roughly over 100 characters) may additionally break
  after a clause-level 「、」 — but first consider splitting it into two
  sentences.
- Exceptions:
  - Commit message bodies follow the git convention (wrap at ~72 columns),
    which takes precedence.
  - Headings, table cells, and list items that are single phrases stay on
    one line as usual.
  - Code comments follow the surrounding code's line-width convention.

</SourceFormatting>

<Style>

- Documentation, README, UI messages: 敬体（です・ます）. One document, one
  register — never mix 敬体 and 常体 in the same prose block.
- Commit messages, PR titles, bullet lists, table cells, headings: 常体 or
  体言止め. 「バグを修正」 not 「バグを修正しました」.
- Code comments: 常体, concise. 「境界値を含む」 not 「境界値を含みます」.
- One sentence, one idea. Prefer short sentences over long 連用中止 chains.
- Avoid redundant honorifics in technical text (「〜させていただく」→
  「〜する」).

</Style>

<Verification>

- If the repo has textlint (or another Japanese prose linter) configured, run
  it on the produced files and fix findings.
- Self-check before finishing: consistent 和欧間スペース, no half-width
  punctuation in Japanese prose, one register per document, terminology table
  respected, long-vowel form uniform.

</Verification>
