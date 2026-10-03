---
name: japanese-writing
description: >-
  Use when writing, rewriting, proofreading or diagnosing Japanese deliverable
  text: articles, blog/note posts, essays, messages and business documents
  (議事録, 文字起こしからの議事録, レポート, 報告書, ガイド, マニュアル, 企画書,
  提案書, メール, スライド構成). Triggers include 読みやすくして, わかりやすく,
  自然な日本語に, AIっぽい, AI臭い, 機械翻訳っぽい, 推敲, リライト, 校正,
  結論から書いて, 表記ゆれ, 和欧混植, この文章を採点して. Provides a design,
  draft, inspect and converge workflow, readability and expression catalogs,
  Microsoft-style notation defaults, doctype guides, a 0-100 naturalness
  diagnosis with a six-axis final review, and a read-only inspector script.
  Scores describe reader cost, never authorship. Not for ordinary
  conversation, translation-file (i18n) tooling, or Markdown formatting alone.
---

## 対象と優先順位

日本語の成果物を書くとき、直すとき、診断するときに使います。
チャットに出力する記事やメッセージ案も対象です。
通常の会話、翻訳ファイルの管理、Markdown の整形だけの作業は対象外です。

優先するのは次の順です。

1. 依頼の指示、文書やリポジトリの規約、媒体の規定
2. 既存の文章で一貫している文体と表記
3. このスキルの既定値

読み手、目的、文書の構成を呼び出し側が決めている場合は、それに従います。
Hermes Writer のように独自の手順を持つ呼び出し側では、その手順の中でこのスキルの知識と検査を使います。

## 基本の考え方

- **意味を保ちます**。主張、比重、確信度、文の働きを変えず、原文にない事実を足しません (references/revision.md R1、R2)。
  別の言い方ができることは、直す理由になりません。
- **書く前に防ぎます**。読み手、目的、骨格を先に決め、執筆の原則に沿って書けば、後で直す箇所は減ります。
- **見つけるのは道具、決めるのは書き手です**。検査器は候補を返すだけです。指摘ごとに直すか、理由を付けて残すか、情報不足かを決めます。
- **素材の不足は文体では直りません**。具体的な事実が足りないときは、集めるか尋ねます。名前、数値、経験を作りません。

## 依頼の種類とモード

| 依頼 | 例 | 進め方 |
|---|---|---|
| 書く | 「〜について記事を書いて」「議事録にまとめて」 | 下のワークフローの 1 から 7 |
| 直す | 「読みやすくして」「AI っぽさを消して」「推敲して」 | 1 で原文の読み手と目的を確かめ、3 で原文を検査し、4 で判断して直し、直した文を original 付きで再び検査して 5 から 7 へ。2 は飛ばす |
| 診断する | 「この文章を採点して」「どれくらい不自然?」 | references/evaluation.md の「診断」に従う (検査は references/inspection.md)。原文は変えない |
| 表記を整える | 「表記ゆれを直して」 | references/notation.md と notation モードで直す。ほかの手順は不要 |

診断の後に書き直すのは、改めて依頼されたときだけです。

作業の深さは 2 段階です。

- **quick (既定)**: 骨格は頭の中で設計し、検査は少なくとも 1 回実行します。
  仕上げは 6 つの観点 (自然さ、密度と簡潔さ、機能と見通し、論理の明確さ、誠実さ、主張の裏付け) を頭の中で確かめるだけです。
- **full**: 社外や経営層に出す文書、1 万字を超える文書、「しっかり」「丁寧に」と頼まれたときに使います。
  骨格を書き出し、検査を全モードで実行し、仕上げの評価 (references/evaluation.md) を点数付きで行います。
  レビュー役のサブエージェントを使える環境では、骨格、読みやすさ、表現の 3 観点のレビューを並行して任せ、統合と判断は自分で行います。
  本文の執筆は分担しません。

判断に迷うときは quick で進め、full にできることを報告に添えます。
full の手順を黙って省きません。省いたときは、省いた手順を報告します。

## ワークフロー

### 1. 設計

- 読み手と、読んだ後に読み手がすることを決めます。分からなければ尋ねます。
- 文書型が合えば、該当する references/doctypes/ のファイルを読みます (議事録 minutes.md、レポート report.md、ガイド guide.md、メモ・企画書・提案書 memo.md、スライド slide.md)。
  エッセイなど該当しない文書では読みません。
  技術、ビジネス、エッセイ、やさしい日本語に当たるなら references/genres.md で調整します。どれとも決めにくければ genre は default です。
- 主なメッセージを一文で書きます。書けなければ、素材が足りないサインです。
- 見出しを並べ、見出しだけで論旨が追えるか確かめます。重要な節は厚く、軽い節は軽く配分します。
- 新しく書く文章では、必要な固有名詞、数値、例、一次情報を先に集めます。集められなければ依頼者に尋ねます。
  すぐに答えが得られないときは、本文の該当箇所に【要確認: 内容】と印を付けて書き進め、報告の確かめたい点に挙げます。
- 利用者の文体プロファイルがあれば読みます。作るのは依頼されたときだけです (assets/style-profile-template.md)。

### 2. 執筆

references/constitution.md の 12 条を守って書きます。
表記は references/notation.md に従います。
執筆中は内容に集中し、細かな言い回しは検査で拾います。

### 3. 検査

references/inspection.md に従って `scripts/inspect_text.py` を実行します。
直す作業では、まず原文を検査し、直した後は直す前の本文を original に渡して revision モードも実行します。
検査用のファイルは成果物とは別の一時ディレクトリに置くか、`--request` で標準入力から渡します。
実行できないときは「未検査」と報告し、inspection.md の手作業の確認に切り替えます。
自動インストールや権限の追加はしません。

### 4. 判断

指摘を一つずつ、直す、残す (理由付き)、情報不足のどれかに分類します (references/revision.md「判断台帳」)。
直し方は、指摘の reason の末尾にある項目を読んで決めます。

| 指摘の参照先 | 読むファイル |
|---|---|
| expression.md X1 から X10 | references/expression.md |
| readability.md A1 から J3 | references/readability.md |
| notation.md N1 から N11 | references/notation.md |
| revision.md R1 から R5 | references/revision.md |

機械的な置き換えはしません。文脈上そのままがよい箇所は残します。

### 5. 骨格と読みやすさの見直し

outline モードの結果で、見出しと各段落の最初の文だけを読み、論旨、見出しの役割、同じ型の繰り返し、節の厚さの配分を確かめます。
文書型のファイルの「必須の要素」と「よくある失敗」と照らします。
reading-load の指摘があるときや、読み直して引っかかる箇所があるときは、references/readability.md の A から J の順に、読み手の負担が大きいものから見ます。

### 6. 収束

直したら同じモードで検査し直し、新しい指摘だけを判断します (references/revision.md「収束」)。
同じ箇所が 2 回続けて形を変えて指摘されるときは、その直しをやめます。

### 7. 仕上げ

references/evaluation.md の 6 つの観点で確かめます。
full では各観点 90 点以上、平均 92 点以上を合格とし、直しは 2 回までにします。
作業用の台帳、JSON、バックアップのファイルは残しません。残すのは成果物と、依頼された文体プロファイルだけです。

## 報告

- 書いたとき: 成果物に加え、確かめたい点があれば短く添えます。full では評価の結果も添えます。
- 直したとき: references/revision.md「直したときの報告」の形 (変えたところ、残した表現、確かめたい点) で報告します。
- 診断したとき: references/evaluation.md「診断の報告」の形で報告します。
- 表記を整えたとき: 整えた本文と、変更の種類ごとの件数を報告します。意味に関わる疑問 (数の食い違いなど) は直さずに確かめたい点に挙げます。
- 検査を実行できなかったモードは「未検査」と書き、「問題なし」と書きません。

## 参照の読み分け

| ファイル | 読むとき |
|---|---|
| references/constitution.md | 書くとき、骨格を直すとき |
| references/readability.md | 読みにくさを直すとき、reading-load の指摘を判断するとき |
| references/expression.md | AI っぽさ、不自然さを直すとき、naturalness と expression の指摘を判断するとき |
| references/notation.md | 表記を決めるとき、notation の指摘を判断するとき |
| references/revision.md | 既存の文章を直すとき、指摘を判断するとき、報告するとき |
| references/genres.md | 技術、ビジネス、エッセイ、やさしい日本語で既定を調整するとき |
| references/doctypes/*.md | 議事録、レポート、ガイド、企画書・提案書・メモ、スライドを書くとき |
| references/evaluation.md | 診断するとき、仕上げの評価をするとき |
| references/inspection.md | 検査を実行するとき、結果を読むとき |
| assets/style-profile-template.md | 文体プロファイルの作成を依頼されたとき |
