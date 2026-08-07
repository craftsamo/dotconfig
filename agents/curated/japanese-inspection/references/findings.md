# lint カテゴリ別の対応方針

`scripts/lint.py` が返す finding はカテゴリごとに性格が違う。
この表は「そのカテゴリが何を疑っているか」と「直すならどの方向か」を引くための一覧である。
2026-07 のコーパス校正（人間 103 文書 + AI 81 文書の実測）で複数の検出器の前提が実データと逆だったことがわかり、方向の反転・削除・格下げを行った。
その経緯も各行に残してある。

| カテゴリ | 何を疑うか | 修正の方向 |
|---|---|---|
| `forbidden_phrase` | LLM 常套句と結論の押し付け（一部の語は severity=info の弱いシグナル） | `forbidden-patterns.md` の該当分類を読み、その表現が本当に必要かを検討する。多くは削れるか、より具体的な言い方に置き換えられる |
| `translationese` / `translationese_morph` | 「〜することができる」などの英語直訳調 | `translationese.md` の対応パターンを引き、Before/After の型に沿って書き直す |
| `antithesis_repetition` | 「〜ではなく」型の対比が 3 回以上。2026-07 の再校正で、出現ごとの一律 critical をやめ「検出数/総文数」の比率で severity を 3 段階化した | severity=info は参考情報（人間の修辞技法と区別のつかない薄い頻度）。warn/critical は比率が高く、実測で真陽性の多い帯。severity にかかわらず全部を直す必要はなく、最も重要な対比だけを残して他は素直な肯定文や具体例に変える |
| `low_sentence_variance` | 文長が均質でリズムが単調 | 一番言いたい文を思い切って短くするか、背景説明の文をあえて長く続ける。短文と長文を意図的に隣接させる |
| `low_burstiness` | 文長のメリハリが乏しい。コーパス実測で AI 86% vs 人間 8〜16% と強い弁別力が確認されている | 同上。他の検出器より信頼度の高いシグナルとして扱ってよい |
| `nominal_ending` | 反転済み: 体言止めが「1 つもない」ことを、人間的修辞の欠如の疑いとして見る（多用の検出ではない） | 体言止めを増やせという意味ではない。機械的に足すとかえって不自然になりやすいので、他の finding と合わせた総合判断の参考情報にとどめる |
| `paragraph_lead_conjunction` | 段落頭の接続詞が多い（EXPERIMENTAL、デフォルト無効。`--experimental` でのみ出力） | 接続詞なしで前の段落とつながる書き方を探す。無理なら残してよい |
| `uniform_paragraph_structure` | 段落あたりの文数が揃いすぎている | 濃淡設計（`japanese-business-docs` の `references/design.md`）に立ち返り、重要な段落を長く、そうでない段落を短くする |
| `repeated_sentence_lead` | 文頭の型の使い回し。閾値を 3→6 に引き上げ、severity を info に格下げ済み（人間の意図的な反復技法と区別がつかないため） | 冒頭の言い回しを変えるか、その文自体を疑問形・体言止め・引用始まりなど別の構造に組み替える。ただし強く直すべき指摘ではない |
| `repeated_syntax_template` | 構文テンプレートの使い回し（EXPERIMENTAL、デフォルト無効） | 同上 |
| `low_lexical_diversity_ttr` / `_mtld` | 語彙の使い回し。文書長 4000 字未満はスキップ（それ以下では統計として機能しないことをコーパスで確認済み） | 類語辞典的な言い換えではなく、より具体的な語（固有名詞、数値、感覚的な描写）への置き換えを探す |
| `low_specificity` | 固有名詞・数値・実例のない一般論段落（info） | 書き方でなく素材の問題。`japanese-business-docs` の `references/design.md` の「素材不足の分岐」に従い、素材を集め直してから書き直す |
| ~~`nested_attributive`~~ | 削除済み（連体修飾の入れ子）。コーパス校正でほぼ全文書型に発火（人間 85% 以上、AI も同水準）し、閾値調整では救えない弁別力ゼロの検出器と判明したため廃止 | 機械検出は不可。`translationese.md` の連体修飾節の Before/After、または `readability-antipatterns.md` の「係り受けの曖昧さ」を手がかりに人手で判断する |
| `english_syntax_inanimate_subject` / `inanimate_subject_morph` | 無生物主語 + 他動詞 | 主語を人や状況に戻すか、述語を状態描写に変える |
| `english_syntax_cleft_because` | 「それは〜。なぜなら〜」型（EXPERIMENTAL、デフォルト無効） | 理由を先に書くか、1 文にまとめる |
| `high_bold_density` / `high_bullet_ratio` / `boilerplate_heading` / `numbered_phase_structure` / `high_emoji_symbol_density` | Markdown 構造レベルの教科書的 AI 癖（太字多用、箇条書き偏重、「まとめ」などの定型見出し、番号つきフェーズ構造、絵文字・装飾記号の多用）。すべて EXPERIMENTAL、デフォルト無効 | `--experimental` で出力させたうえで構成を見直す。太字を減らす、箇条書きの一部を地の文へ戻す、定型見出しをやめて内容そのもので締める |

EXPERIMENTAL 系（`--experimental` を付けない限り出力されない）は、コーパスでの定量校正がまだか、human/ai ともほぼ発火しないと判定された検出器である。
校正が進むまで、判断材料としての信頼度は低いものとして扱う。

`--genre essay|tech|business` を指定すると、ジャンル別にコーパス校正した閾値プロファイルへ切り替わる（未指定時は共通の保守的閾値）。
ジャンルごとの判断の重みづけは `genre-notes.md` を参照。

すべての finding を機械的に潰す必要はない。
検出は疑いの提示にすぎず、文脈上そのままで自然な箇所も混じっている。
判断に迷ったら、その一文を声に出して読み、実際に人が話すときの言い回しに近いかどうかで決める。
