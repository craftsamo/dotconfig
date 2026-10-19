# 検査の使い方

`scripts/inspect_text.py` は、日本語の文章を読み取るだけの検査器です。
読み直す候補、文書の骨格、用語、書式の数値、機械スコアを JSON で返します。
原文の変更、文書の設計、合否の判断はしません。指摘は revision.md の判断台帳で一つずつ判断します。

## 実行のしかた

スキルのディレクトリで、Python 3.10 以上を使って実行します。
ファイルの書き込み、ネットワーク接続、パッケージのインストールはしません。

```sh
python3 -B scripts/inspect_text.py --file draft.md
python3 -B scripts/inspect_text.py --file draft.md --modes naturalness,reading-load --genre tech
python3 -B scripts/inspect_text.py --file after.md --original before.md --stance explanation
```

JSON を標準入力で渡す形もあります。ツールから呼び出すときはこちらを使います。

```sh
python3 -B scripts/inspect_text.py --request < request.json
```

| フィールド | 値 | 既定 |
|---|---|---|
| text | 検査する本文 (必須、UTF-8 で 131072 バイトまで) | なし |
| modes | 下表のモード名の配列 | revision 以外のすべて (original があれば revision も) |
| genre | default、tech、business、essay (genres.md) | default |
| experimental | true で naturalness の実験的な規則も実行 | false |
| stance | advice、rule、explanation (revision.md R3) | なし |
| original | 直す前の本文。revision モードでだけ使う | なし |

Hermes Writer など専用のツールがある環境では、そのツールを使います。
シェルを使えない環境では、この後の「検査を実行できないとき」に従います。

### 形態素解析

いくつかの規則は SudachiPy を使います。
`scripts/requirements.txt` と同じ版 (SudachiPy 0.6.11、sudachidict_core 20260723) が実行する Python に入っていれば使われます。
入っていなければ、その規則は unverified になり、ほかの規則だけが実行されます。
自動でインストールはしません。
指定の版が入った Python がすでにあれば、それを使って構いません。
部分的な結果 (partial) と、すべての規則を実行した結果の両方があれば、後者を報告します。
uv が使え、パッケージの取得が許されている環境では、次の形で指定の版を使えます。

```sh
uv run --with SudachiPy==0.6.11 --with sudachidict_core==20260723 python -B scripts/inspect_text.py --file draft.md
```

## モード

| モード | 返すもの | 形態素解析 | 主な参照 |
|---|---|---|---|
| naturalness | 決まり文句、翻訳調、対比の反復、リズムの均質さ、語彙、具体性の指摘と score | 一部 | expression.md |
| expression | 比喩動詞、空疎な語、前置き、文末の連続、太字の描画、太字と箇条書きの多さ、文体の混在 | 不要 | expression.md、notation.md N11 |
| notation | 表記の既定値からのずれ | 不要 | notation.md |
| reading-load | 長い一文、漢字の連続、埋もれた列挙、二重否定、「の」の連鎖 | 一部 | readability.md |
| outline | 見出し、段落の最初の文、箇条書きのまとまりと、見出しの統計 (heading_stats) | 一部 | doctypes/*.md |
| terms | カタカナ語、略語、固有名詞と、最初の出現の近くに説明があるかの手がかり | 一部 | readability.md J2 |
| structure | 太字、箇条書き、見出しの数と比率 | 不要 | constitution.md 第 3 条、第 6 条 |
| revision | 直す前後の差分: 意味を表す表現の増減、消えた語と増えた語、構成の変化、論理のつながり、文末の変化 | 不要 | revision.md |

作業ごとの目安です。

| 作業 | モード |
|---|---|
| 書く | naturalness、expression、notation、reading-load、outline。用語の多い文章は terms も |
| 直す | 上に加えて revision (original に直す前の本文) |
| 診断する | naturalness、reading-load。full なら outline も |
| 表記だけ整える | notation |

## 結果の読み方

- **status**: ok は全規則を実行したこと、partial は一部が未検査か結果を省略したこと、error は結果がないことを表します。
  partial でも終了コードは 0 です。
- **unverified**: 実行できなかった規則と理由です。そのモードは「未検査」と報告し、「問題なし」としません。
- **findings**: mode、rule_id、severity (info、warn、critical)、line、column (1 始まりの文字位置)、excerpt、reason、related_lines を持ちます。
  reason の末尾の括弧は、読むべき参照の項目です。
- **score**: naturalness を実行したときの機械スコアです (evaluation.md)。value が null のときは reason を見ます。
- **outline**、**heading_stats**、**terms**、**structure**、**revision**: 判断の材料です。合否の基準ではありません。
- **stats**: モードごとの集計値です。
- **truncation**: 指摘、骨格、用語はそれぞれ 200 件までです。省略した件数は counts に入ります。
  抜粋は 240 文字までです。

指摘は候補です。同じ箇所に複数のモードが別の観点から指摘することもあります。
文書全体についての指摘 (文長のばらつき、語彙の幅など) は、最初の文や最初の段落の行に付きます。その行だけの問題ではありません。
stats の文字数や文数は、モードごとに数える範囲 (地の文だけか、見出しや箇条書きを含むか) が違うため、一致しないことがあります。
指摘ゼロは文章の質の証明ではなく、指摘ゼロを目標にもしません。

## 長い文章

1 回で渡せる本文は 131072 バイト (日本語でおよそ 4 万字) までです。
これを超える文章は節ごとに分けて検査し、どの範囲を検査したかを書きます。
分けて検査したときは、文書全体の比率や score を合算しません。

## 解析の限界

- Markdown は限定的に解釈します。front matter、コード ブロック、インライン コード、HTML のコメントとタグ、引用、表、リンク先は検査しません。
- 文の候補は物理的な行をまたぎません。1 文を途中で改行している文章では、文が短く数えられます。
- 文の区切りは「。」「!」「?」と、後ろに空白が続く半角の「?」「!」です。
- 語のリストと閾値は経験則です。文脈で判断します。

## 検査を実行できないとき

シェルがない、Python がないなどで実行できないときは、検査を「未検査」と報告したうえで、次を手で確かめます。

1. 決まり文句と前置き、締め (expression.md X1)
2. 翻訳調と無生物主語 (X3、X4)
3. 「ではなく」の対比が繰り返されていないか (X6)
4. 文の長さと文末が単調でないか (X7)
5. 一文が長すぎないか、二重否定、「の」の連鎖 (readability.md B1、A1、C2)
6. 見出しと各段落の最初の文だけで論旨が追えるか (constitution.md 第 2 条)
7. 用語を説明してから使っているか (readability.md J2)
8. 表記 (notation.md N1 から N7)

手で確かめた結果に点数は付けません。
