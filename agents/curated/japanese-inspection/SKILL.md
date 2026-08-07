---
name: japanese-inspection
description: Use to inspect, diagnose, or de-AI-flavor any Japanese deliverable text — mechanical detection plus a judgment loop that converges (AIっぽい, AI臭い, AI臭さの除去, 機械翻訳っぽい, 不自然, もっと自然な日本語に, 人間っぽくして, 単調, 読みにくい, わかりにくい, 語順がおかしい, 一文が長い, 読点の位置, 何が言いたいか分からない, この文章AIが書いた?, AI臭さをスコアで, 採点して, 診断して, 推敲, リライト). Runs deterministic detectors via uv (scripts/lint.py --json with --genre essay|tech|business profiles and --baseline convergence tracking; scripts/outline.py skeleton extraction; scripts/terms.py term-explanation audit), routes every finding through a fix-or-keep ledger (判断台帳) — detection is mechanical, judgment stays with the agent — and loops until converged, with divergence guards and anti-sweep rewrite rules for existing documents. Includes a no-rewrite score mode (0-100 naturalness, bands, reasons), plus judgment catalogs: forbidden LLM phrases, translationese syntax, readability principles, 24 bad-sentence antipatterns, and per-genre threshold notes. This is the cross-cutting inspection layer of the Japanese writing stack — layer it onto drafts from `japanese-writing` / `japanese-tech-prose` / `japanese-business-docs` / `japanese-prose-rhythm`; it repairs and judges text but does not own document design or notation rules. Requires uv for the scripts (catalogs still work as manual checklists without it).
---

<Goal>

日本語の成果物テキストから AI 臭さと読みにくさを取り除く、横断的な検査層。
軸は「検出は機械、判断は AI」である。
AI は自分の癖を認識しにくいという前提に立ち、疑いの検出は機械が決定的に行い、直すかどうかは文脈を見て AI（あなた）が判断する。
検出結果は判断台帳で仕分け、修正が新しい指摘を生まなくなるまでループを回して収束させる。

</Goal>

<WhenToApply>

対象: 日本語で書かれ、成果物として残るあらゆるテキストの検査・推敲・リライト。
他の日本語スキルで書いた下書きへの仕上げの検査（`japanese-business-docs` の工程 5、`japanese-tech-prose` と `japanese-prose-rhythm` の Verification）。
「AI っぽい」「読みにくい」「もっと自然に」という指摘への対応。
書き換えを伴わない診断・採点の依頼（<Diagnose>）。

対象外: 文書の設計と執筆そのもの。
何を書くかは `japanese-business-docs`（ビジネス文書）や `japanese-tech-prose`（解説プロース）が持ち、本スキルは書かれたものを検査する。
表記・用語の規則は `japanese-writing` が持つ（検査で見つかる表記ゆれの正解はそちらを引く）。

</WhenToApply>

<Scripts>

検出器は `uv` で実行する（依存は各スクリプトの PEP 723 メタデータで自動解決される）。
ファイルパスは本スキルのディレクトリからの相対で示す。

```
uv run scripts/lint.py <file.md> --json [--genre essay|tech|business] [--baseline <prev.json>] [--experimental]
uv run scripts/outline.py <file.md>   # 見出し・各段落の先頭文・箇条書きプレースホルダを行番号付きで抽出
uv run scripts/terms.py <file.md>     # カタカナ複合語・ASCII略語・固有名詞らしき語を初出行・出現回数・説明マーカーの有無つきで列挙
```

- `lint.py` は禁止語、翻訳調、否定肯定対比の反復、文長の均質さ、体言止めの欠如、語彙多様性、英語統語の疑いなどを決定的に検出する。CI ゲートではなく lint なので、検出件数にかかわらず exit code は 0。入力エラーのときだけ 1 になる
- ジャンルが明確なら `--genre` を必ず指定する。コーパス校正済みの閾値プロファイルに切り替わり、誤検知が減る
- 収束ループでは直前の `--json` 出力を `--baseline` に渡す。resolved / new / persisting が自動で仕分けられる
- `outline.py` と `terms.py` は判断せず素材を抽出するだけである。構造レビューと用語初出チェックの材料に使う（説明済みかどうかの判断は AI が行う）
- 文書が短くても lint は省略しない。統計系の検出器は短文で沈黙するが、禁止語と翻訳調は文 1 つでも検出される。数秒の保険であり、飛ばした時点で検査の品質保証は成立しない

</Scripts>

<Workflow>

1. **lint** — `--json` で実行し、finding を得る。ジャンルがわかるなら `--genre` を付ける
2. **判断** — finding は疑いの提示であって指示ではない。ヒットしたカテゴリを `references/findings.md` で引き、迷う場合は該当カタログ（`forbidden-patterns.md` / `translationese.md`）を読み直したうえで、finding ごとに「直した」か「残す（理由）」かを判断台帳へ記録する（台帳の形式と置き場所は `references/revision.md`）
3. **構造・読みやすさレビュー** — lint は文レベルの表層しか見えない。とくに箇条書き主体の議事録・スライドでは lint がほぼ素通りするため、目視レビューが主役になる。`outline.py` で骨組みを抽出して論旨・見出し・鋳型の反復・濃淡・So What を確かめ、`references/revision.md` の「読みやすさレビューの手順」に従って周回ごとの観点を変える。文書型が定まっているなら `japanese-business-docs` の doctype の「必須要素」「AI がやりがちな失敗」とも照合する。見つけた問題は lint の finding と同じ台帳に載せる
4. **修正** — 台帳の「直した」項目を反映する。既存文書のリライトでは同種の修正を全項目へ一律に当てない（`references/revision.md` の「スイープ改稿の罠」）
5. **再 lint** — `--baseline` つきで再実行し、新規 finding の有無を確かめる。全 finding が仕分け済みで、修正が新規 finding を生んでいない状態になるまで 2〜5 を繰り返す。同じ finding が 2 周連続で再発したら発散ガード（`references/revision.md`）に従う
6. **最終パス** — 収束は既知パターンの消滅しか意味しない。初見の読者として通読し、声に出して読むつもりでリズムを確かめる（`references/revision.md` の「自己点検ループ」）。違和感が出たら台帳に起こして 5 に戻る
7. **後片付け** — 台帳ファイル、lint の JSON、途中版バックアップなどの中間ファイルをすべて削除する（`references/revision.md` の「作業ファイルの扱い」）

</Workflow>

<Diagnose>

書き換えずにスコアと理由だけを返す依頼（「この文章 AI が書いた?」「AI 臭さを採点して」）では、**最初に必ず `references/diagnose.md` を読む**。
スコアの算出式、バンド、出力形式の定義がそこにある。
これを読まずに lint findings の転記で返した時点で、診断モードの仕事にならない。
診断後にリライトを提案してよいが、頼まれるまで直さない。

</Diagnose>

<References>

- `references/findings.md` — lint カテゴリ別の「何を疑うか」「修正の方向」。判断の最初の入口
- `references/forbidden-patterns.md` — 禁止語と LLM 常套句のカタログ（理由つき）
- `references/translationese.md` — 英語統語が透ける翻訳調のパターンと書き直しの型
- `references/readability-principles.md` — 語順、読点、一文一義、主語述語の距離など、機械閾値化できない読みやすさの一般原則
- `references/readability-antipatterns.md` — 悪文パターンのカタログ
- `references/genre-notes.md` — ジャンル（tech/business/essay/公用文）ごとの判断の重みづけと許容される逸脱
- `references/revision.md` — 判断台帳、読みやすさレビュー手順、スイープ改稿の罠、発散ガード、収束条件、自己点検ループ、作業ファイルの扱い
- `references/diagnose.md` — 診断モード（score）の算出式と出力形式

読みやすさの修正で短さを目的関数にしない。
事実の保持と主述・係り受けを確認したあとの同等候補間でだけ、タイブレーカーとして短さを使う。

</References>
