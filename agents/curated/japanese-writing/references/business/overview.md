# ビジネス文書層：仕事の文書の設計と執筆

<Goal>

この層は、日本語で書かれている、

- 議事録
- 調査レポート
- 社内ガイド
- リサーチのメモ
- 企画書
- スライドの構成

といった仕事の文書を、読みやすく（わかりやすく）書く（直す）ための規範です。
「事後修正より生成時制約」を軸にします。
書いたあとに癖を消すより、書く前の設計と書くときの制約で発生自体を防ぐほうが効くからです。
機械検出と収束ループによる事後の検査は検査層（`references/inspection/workflow.md`）が受け持ち、この層は設計と執筆を受け持ちます。

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
「結論から書いて」「論旨を明確に」「見出しを端的に」「専門用語をわかりやすく」といった指示にもこの層で応えます。

解説記事、チュートリアル、技術書の章は対象外です（論証層 `references/tech-prose.md` が受け持ちます）。
読み物として読ませる記事やエッセイも対象外です（`references/tech-prose.md` に `references/prose-rhythm.md` を重ねます）。
API リファレンスやコミットメッセージなどの短い定型文は、SKILL.md の表記層だけで足ります。

表記、用語、和欧混植、一文一行の規則は、SKILL.md の表記層が持ちます。
ビジネス文書に緩急層（`references/prose-rhythm.md`）を重ねてはなりません。
走査して読まれる文書では、平坦であることが正しいからです。

</WhenToApply>

<Workflow>

工程は「設計 → 執筆 → 検査」の順に進みます。

1. **読者・目的・文書型の特定**：誰が読み、読んだあとに何が起きてほしい文書かを特定する（不明ならユーザーに聞く）。文書型が定まったら <DoctypeTable> の対応ファイルを読む。
2. **主メッセージとスケルトン**：本文の前に、主メッセージを一文で書く。書けないなら素材不足であり、書き方の問題ではない（`references/business/design.md` の「素材集め」へ）。次に見出しスケルトンを作る。各見出しはラベルでなく結論を含むメッセージにし、見出しだけを順に読んで論旨が通ることを確かめてから本文に進む。
3. **濃淡設計と素材集め**：`references/business/design.md` に従い、節ごとの厚みを割り振り、厚く書く箇所の固有名詞、数値、一次情報を確保する。
4. **執筆**：`references/business/constitution.md` の12条を制約として本文を書く。この段階では細部の禁止語やリズムを気にしすぎず、憲法の範囲で内容を出し切ってよい。細部は次の検査が拾う。
5. **検査**：完成した下書きに検査層（`references/inspection/workflow.md`）を適用する（lint、判断台帳、収束ループ、スケルトン通読）。doctype の「必須要素」と「AI がやりがちな失敗」への照合も検査時に行う。

既存文書のリライトでは、工程を頭から回すのではなく、直す箇所を選びます。
一律適用の禁止と keep/change の割り振りは `references/inspection/revision.md` に従います。

</Workflow>

<DoctypeTable>

文書型ごとの流儀は、次のファイルが持ちます。

| 文書型 | 読むファイル |
| --- | --- |
| 議事録（文字起こしからの議事録化を含む） | `references/business/doctypes/minutes.md` |
| 調査レポート・分析レポート | `references/business/doctypes/report.md` |
| 社内ガイド・マニュアル | `references/business/doctypes/guide.md` |
| リサーチメモ・ディスカッションペーパー・企画書 | `references/business/doctypes/memo.md` |
| スライド構成 | `references/business/doctypes/slide.md` |

型に当てはまらない文書（短いメールや依頼文など）は、doctype を読まず、12条と設計工程だけで書いてかまいません。

</DoctypeTable>

<References>

- `references/business/constitution.md`：文体憲法（生成時の12条）。執筆前に通読し、執筆中は制約として保持する。
- `references/business/design.md`：濃淡設計、素材集め（再帰的推論リサーチ）、素材不足の分岐。
- `references/business/doctypes/`：文書型ごとの必須要素、構成、AI がやりがちな失敗。

</References>

<Verification>

- 納品前にスケルトン通読を行う（`references/business/constitution.md` の「仕上げには見出しと段落先頭だけを読み返す」）。
  `scripts/outline.py` で骨組みを機械抽出できる。
- 検査層のかけ方は `references/inspection/workflow.md` の Workflow に従う。
  ビジネス文書なら lint に `--genre business` を指定する。
- 表記の点検は SKILL.md の Verification に従う。

</Verification>
