# 検査スクリプトの使い方

`scripts/inspect_text.py` は、日本語原稿を読み取り専用で解析するスクリプトです。見直し候補（`findings`）、見出し・段落骨格（`outline`）、用語目録（`terms`）、構造集計（`structure`）、修正前後の差分（`revision`）、機械スコア（`score`）を JSON（schema v2）で返します。ファイルの書き換え、ネットワーク通信、パッケージの自動インストールは一切行いません。

## 実行方法

スキルのディレクトリ基準で Python 3.10 以上から実行します（一時ファイルを作らず `--request` で標準入力から JSON を渡すことも可能です）。Hermes Writer など専用の検査ツール（`writing_inspect`）が用意されている環境ではそちらを呼び出します。

```sh
python3 -B scripts/inspect_text.py --file draft.md
python3 -B scripts/inspect_text.py --file draft.md --modes naturalness,expression,reading-load --genre tech
python3 -B scripts/inspect_text.py --file after.md --original before.md --genre tech --stance explanation
python3 -B scripts/inspect_text.py --request < request.json
```

| フィールド | 指定できる値 | 既定値 |
|---|---|---|
| `text` | 検査対象の本文（必須、UTF-8 で最大 131,072 バイト） | なし |
| `modes` | 実行モードの配列 | `revision` 以外の全モード（`original` 指定時は `revision` も追加） |
| `genre` | `default`、`tech`、`business`、`essay`（references/genres.md） | `default` |
| `experimental` | `true` で `naturalness` の実験規則も実行 | `false` |
| `stance` | `advice`、`rule`、`explanation`（references/revision.md R3） | なし |
| `original` | 修正前の本文（`revision` モード使用時に必須） | なし |

### 形態素解析（SudachiPy）の扱い

一部の規則は `scripts/requirements.txt` で固定された版（`SudachiPy==0.6.11`、`sudachidict_core==20260723`）が Python 環境に入っているときに実行されます。未導入の環境では該当規則が `unverified` として記録され、パターンベースの規則のみが動きます（終了コードは `0`、`status` は `"partial"`）。自動でインストールせず、`unverified` の項目は「未検査」として扱います。

## 各モードの役割と注意点

| モード | 主な検出・出力内容 | 形態素解析 | 主な参照先 |
|---|---|---|---|
| `naturalness` | 定型句、翻訳調、対比の反復、文長・段落の均質さ、語彙多様性、具体性不足と機械スコア | 一部使用 | expression.md |
| `expression` | スロップ語彙、比喩・仕様の擬人化、不自然な和語化・言い換え（`unnatural_paraphrase`）、前置き、地の文の同一文末連続・短文のぶつ切り連続（`choppy_sentence_run`）、太字崩れ、書式密度、敬体・常体の混在 | 不要 | expression.md、notation.md N11 |
| `notation` | 和欧間・単位スペース、括弧の混在、全角英数字・記号、長音、かな書きなどの表記点検 | 不要 | notation.md |
| `reading-load` | 長文、7字以上の漢字連続、埋もれた列挙、二重否定、「の」の3連鎖以上（地の文・箇条書きとも対象） | 一部使用 | readability.md |
| `outline` | 見出し、段落冒頭文、箇条書きブロックの一覧と見出し統計 | 一部使用 | constitution.md、doctypes/*.md |
| `terms` | カタカナ語・略語・固有名詞の初出位置と出現回数（参考目録でありエラーではない） | 一部使用 | readability.md C4・J2 |
| `structure` | 見出し・箇条書き・太字の件数と比率 | 不要 | constitution.md 第3条・第6条 |
| `revision` | 修正前後の表現マーカー増減、消失・追加された内容語、構造変化、文末変化 | 不要 | revision.md |

## 結果を読むときの鉄則

- 指摘ゼロを目標にしない: `findings` は「見直し候補」です。文脈上適切な表現や分野の定型は、無理にいじらず「残す」と判断します（references/revision.md「判断台帳」）。
- **`terms` モードを誤解しない**: `terms` の `has_gloss_hint: false` は「近くに括弧や『とは』がない」という機械的な事実を示すだけです。想定読者が知っている技術用語・カタカナ語を和語に言い換えたり、不要な括弧注釈（`ルート（URL のパス）` など）を追加したりする理由にはなりません。
- **ジャンル（`genre`）を適切に指定する**: GitHub Issue・PR・仕様書・手順書などの技術文書では必ず `--genre tech` を指定してください。`tech` や `business` では箇条書き比率の警告（`excess_list` / `high_bullet_ratio`）が抑制され、仕様列挙を無理に地の文へ崩す誤誘導を防げます。
- 解析範囲の仕様: コードブロック、インラインコード、URL、フロントマター、HTML コメント、引用ブロック、パイプ表は原則として検査から除外またはマスクされます。4万字（131,072バイト）を超える長文は章・節単位に分割して検査し、分割検査時は文書全体スコアを合算しません。

## スクリプトを実行できないときの手動点検

シェルや Python が使えない環境では、機械検査を「未検査」と明記したうえで以下の7点を目視と音読で確認します（手動点検時に点数は付けません）。

1. 語彙の自然さ: 専門用語や自然な二字漢語を、不気味な和語・幼児語（「足す」「当てる」「絵」「置き場」「道筋」など）へ崩していないか（expression.md X11）。
2. 呼吸と行間: 一息でつながる場面を細切れの単文に刻んでいないか、会話や情景の直後に意味をセルフ解説していないか、末尾に予防線を何文も並べていないか（X7、X12）。
3. 前置き・スロップ・思わせぶりな否定: 空疎な導入・まとめ、雰囲気語、「〜わけではない」「A というより B」の連発がないか（X1、X2、X5、X6）。
4. 翻訳調と擬人化: 「〜することが可能」「抽象主語 + もたらす」、仕様の擬人化などがないか（X3、X4）。
5. 一文の負担: 90字を超える詰め込み文、「の」の3連鎖以上、主語と述語のねじれがないか（readability.md B1、B2、C2）。
6. 見出しと箇条書き: 見出しだけで構成が追えるか。経緯が細切れの箇条書きになっていないか、逆に並列要件が長文に埋もれていないか（constitution.md 第2条・第3条）。
7. 意味・誠実さと表記の一貫性: 原文の条件・留保・確信度を変えていないか、手元にない事実を補っていないか（revision.md R1、R2）。敬体・常体（途中の1文混入を含む）、全角・半角括弧、和欧スペース、用語の呼称が文書内で揃っているか（notation.md）。
