---
name: japanese-business-docs
description: Use when writing or revising Japanese business/work documents — meeting minutes (incl. from transcripts), research/analysis reports, internal guides & manuals, research memos / discussion papers / proposals, and slide outlines (議事録, 文字起こしから議事録, 調査レポート, 分析レポート, 社内ガイド, マニュアル, リサーチメモ, ディスカッションペーパー, 企画書, 提案書, 報告書, スライド構成, 結論から書いて, 論旨を明確に, 見出しを端的に, 専門用語をわかりやすく). Covers pre-draft document design (reader/purpose, one-sentence main message, conclusion-bearing heading skeleton, deliberate density contrast, evidence gathering) plus a 12-article generation-time style constitution (conclusion first, headings carry conclusions, causal chains in prose not bullets, function-before-name terms, grounding in names and numbers, bold scarcity, density contrast, no 3x template repeats, negation-contrast only for real misconceptions, explicit certainty labels, fact/opinion separation, So-What closings) and per-doctype patterns under references/doctypes/. This is the business-document layer of the Japanese writing stack — notation lives in `japanese-writing` (always load it too); run `japanese-inspection` on the draft at review time. Do NOT use for long-form explanatory articles/tutorials (that is `japanese-tech-prose`), and never load `japanese-prose-rhythm` for business documents — flat is correct there.
---

<Goal>

本スキルは、日本語で書かれている、

- 議事録
- 調査レポート
- 社内ガイド
- リサーチのメモ
- 企画書
- スライドの構成

といった仕事の文書を、読みやすく（わかりやすく）書く（直す）ための規範です。
「事後修正より生成時制約」を軸にします。
書いたあとに癖を消すより、書く前の設計と書くときの制約で発生自体を防ぐほうが効くからです。
機械検出と収束ループによる事後の検査は `japanese-inspection` が受け持ち、本スキルは設計と執筆を受け持ちます。

</Goal>

<WhenToApply>

仕事の文書の作成と校正が対象です。
具体的には、

- 議事録（文字起こしからの議事録化を含む）
- 調査レポート（分析レポート）
- 社内ガイド（マニュアル）
- リサーチのメモ、ディスカッションペーパー
- 企画書、提案書、報告書、メール
- スライドの構成案

といった文書です。
「結論から書いて」「論旨を明確に」「見出しを端的に」「専門用語をわかりやすく」といった指示にも本スキルで応えます。

解説記事、チュートリアル、技術書の章は対象外です（`japanese-tech-prose` が受け持ちます）。
読み物として読ませる記事やエッセイも対象外です（`japanese-tech-prose` に `japanese-prose-rhythm` を重ねます）。
API リファレンスやコミットメッセージなどの短い定型文は、`japanese-writing` だけで足ります。

表記、用語、和欧混植、一文一行の規則は `japanese-writing` が持ちます。
必ず併読してください。
ビジネス文書に `japanese-prose-rhythm` を重ねてはなりません。
走査して読まれる文書では、平坦であることが正しいからです。

</WhenToApply>

<Workflow>

工程は「設計 → 執筆 → 検査」の順に進みます。

1. **読者・目的・文書型の特定**：誰が読み、読んだあとに何が起きてほしい文書かを特定する（不明ならユーザーに聞く）。文書型が定まったら <DoctypeTable> の対応ファイルを読む。
2. **主メッセージとスケルトン**：本文の前に、主メッセージを一文で書く。書けないなら素材不足であり、書き方の問題ではない（`references/design.md` の「素材集め」へ）。次に見出しスケルトンを作る。各見出しはラベルでなく結論を含むメッセージにし、見出しだけを順に読んで論旨が通ることを確かめてから本文に進む。
3. **濃淡設計と素材集め**：`references/design.md` に従い、節ごとの厚みを割り振り、厚く書く箇所の固有名詞、数値、一次情報を確保する。
4. **執筆**：`references/constitution.md` の12条を制約として本文を書く。この段階では細部の禁止語やリズムを気にしすぎず、憲法の範囲で内容を出し切ってよい。細部は次の検査が拾う。
5. **検査**：完成した下書きに `japanese-inspection` を適用する（lint、判断台帳、収束ループ、スケルトン通読）。doctype の「必須要素」と「AI がやりがちな失敗」への照合も検査時に行う。

既存文書のリライトでは、工程を頭から回すのではなく、直す箇所を選びます。
一律適用の禁止と keep/change の割り振りは `japanese-inspection` の `references/revision.md` に従います。

</Workflow>

<DoctypeTable>

文書型ごとの流儀は、次のファイルが持ちます。

| 文書型 | 読むファイル |
| --- | --- |
| 議事録（文字起こしからの議事録化を含む） | `references/doctypes/minutes.md` |
| 調査レポート・分析レポート | `references/doctypes/report.md` |
| 社内ガイド・マニュアル | `references/doctypes/guide.md` |
| リサーチメモ・ディスカッションペーパー・企画書 | `references/doctypes/memo.md` |
| スライド構成 | `references/doctypes/slide.md` |

型に当てはまらない文書（短いメールや依頼文など）は、doctype を読まず、12条と設計工程だけで書いてかまいません。

</DoctypeTable>

<References>

- `references/constitution.md`：文体憲法（生成時の12条）。執筆前に通読し、執筆中は制約として保持する。
- `references/design.md`：濃淡設計、素材集め（再帰的推論リサーチ）、素材不足の分岐。
- `references/doctypes/`：文書型ごとの必須要素、構成、AI がやりがちな失敗。

</References>

<Verification>

- 納品前にスケルトン通読を行う（`references/constitution.md` の「仕上げには見出しと段落先頭だけを読み返す」）。
  `japanese-inspection` の `scripts/outline.py` で骨組みを機械抽出できる。
- 検査層のかけ方は `japanese-inspection` の Workflow に従う。
  ビジネス文書なら lint に `--genre business` を指定する。
- 表記の点検は `japanese-writing` の Verification に従う。

</Verification>
