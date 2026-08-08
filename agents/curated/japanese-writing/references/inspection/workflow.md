# 検査層：AI 臭さと読みにくさの検出と収束

<Goal>

この検査層は、日本語の成果物テキストから AI 臭さと読みにくさを取り除きます。
どの層で書いた成果物にも、横断的にかけます。
「検出は機械、判断はエージェント」を軸にします。
AI は自分の癖を認識しにくいという前提に立ち、疑いの検出は機械が決定的に行い、直すかどうかは文脈を見てエージェントが判断します。
検出結果は判断台帳で仕分け、修正が新しい指摘を生まなくなるまでループを回して収束させます。

</Goal>

<WhenToApply>

日本語で書かれていて、成果物として残るあらゆるテキストの検査（推敲、リライト）が対象です。
他の日本語スキルで書いた下書きへの仕上げの検査（`references/business/overview.md` の工程5、`references/tech-prose.md` と `references/prose-rhythm.md` の Verification）もここで受けます。
「AI っぽい」「読みにくい」「もっと自然に」という指摘への対応も対象です。
書き換えを伴わない診断（採点）の依頼は <Diagnose> が受けます。

文書の設計と執筆そのものは対象外です。
何を書くかはビジネス文書層（`references/business/overview.md`）や論証層（`references/tech-prose.md`）が持ち、この層は書かれたものを検査します。
表記と用語の規則は SKILL.md の表記層が持ちます（検査で見つかる表記ゆれの正解はそちらを引きます）。

</WhenToApply>

<Scripts>

検出器は `uv` で実行します（依存は各スクリプトの PEP 723 メタデータで自動解決されます）。
ファイルパスはスキルのルートディレクトリからの相対で示します。

```
uv run scripts/lint.py <file.md> --json [--genre essay|tech|business] [--baseline <prev.json>] [--experimental]
uv run scripts/outline.py <file.md>   # 見出し・各段落の先頭文・箇条書きプレースホルダを行番号付きで抽出
uv run scripts/terms.py <file.md>     # カタカナ複合語・ASCII略語・固有名詞らしき語を初出行・出現回数・説明マーカーの有無つきで列挙
```

- `lint.py` は、禁止語、翻訳調、否定肯定対比の反復、文長の均質さ、体言止めの欠如、語彙多様性、英語統語の疑いなどを決定的に検出する。
  CI ゲートではなく lint なので、検出件数にかかわらず exit code は0。入力エラーのときだけ1になる。
- ジャンルが明確なら `--genre` を必ず指定する。
  コーパス校正済みの閾値プロファイルに切り替わり、誤検知が減る。
- 収束ループでは、直前の `--json` 出力を `--baseline` に渡す。
  resolved / new / persisting が自動で仕分けられる。
- `outline.py` と `terms.py` は判断せず、素材を抽出するだけである。
  構造レビューと用語初出チェックの材料に使う（説明済みかどうかの判断はエージェントが行う）。
- 文書が短くても lint は省略しない。
  統計系の検出器は短文で沈黙するが、禁止語と翻訳調は文1つでも検出される。
  数秒の保険であり、飛ばした時点で検査の品質保証は成立しない。

</Scripts>

<Workflow>

1. **lint**：`--json` で実行し、finding を得る。ジャンルがわかるなら `--genre` を付ける。
2. **判断**：finding は疑いの提示であって指示ではない。ヒットしたカテゴリを `references/inspection/findings.md` で引き、迷う場合は該当カタログ（`forbidden-patterns.md` / `translationese.md`）を読み直したうえで、finding ごとに「直した」か「残す（理由）」かを判断台帳へ記録する（台帳の形式と置き場所は `references/inspection/revision.md`）。
3. **構造・読みやすさレビュー**：lint は文レベルの表層しか見えない。とくに箇条書き主体の議事録やスライドでは lint がほぼ素通りするため、目視レビューが主役になる。`outline.py` で骨組みを抽出して論旨、見出し、鋳型の反復、濃淡、So What を確かめ、`references/inspection/revision.md` の「読みやすさレビューの手順」に従って周回ごとの観点を変える。文書型が定まっているなら `references/business/doctypes/` の「必須要素」「AI がやりがちな失敗」とも照合する。見つけた問題は lint の finding と同じ台帳に載せる。
4. **修正**：台帳の「直した」項目を反映する。既存文書のリライトでは、同種の修正を全項目へ一律に当てない（`references/inspection/revision.md` の「スイープ改稿の罠」）。
5. **再 lint**：`--baseline` つきで再実行し、新規 finding の有無を確かめる。全 finding が仕分け済みで、修正が新規 finding を生んでいない状態になるまで2〜5を繰り返す。同じ finding が2周連続で再発したら発散ガード（`references/inspection/revision.md`）に従う。
6. **最終パス**：収束は既知パターンの消滅しか意味しない。初見の読者として通読し、声に出して読むつもりでリズムを確かめる（`references/inspection/revision.md` の「自己点検ループ」）。違和感が出たら台帳に起こして5に戻る。
7. **後片付け**：台帳ファイル、lint の JSON、途中版バックアップなどの中間ファイルをすべて削除する（`references/inspection/revision.md` の「作業ファイルの扱い」）。

</Workflow>

<Diagnose>

書き換えずにスコアと理由だけを返す依頼（「この文章 AI が書いた?」「AI 臭さを採点して」）では、**最初に必ず `references/inspection/diagnose.md` を読みます**。
スコアの算出式、バンド、出力形式の定義がそこにあります。
これを読まずに lint findings の転記で返した時点で、診断モードの仕事になりません。
診断後にリライトを提案してもかまいませんが、頼まれるまで直しません。

</Diagnose>

<References>

- `references/inspection/findings.md`：lint カテゴリ別の「何を疑うか」「修正の方向」。判断の最初の入口。
- `references/inspection/forbidden-patterns.md`：禁止語と LLM 常套句のカタログ（理由つき）。
- `references/inspection/translationese.md`：英語統語が透ける翻訳調のパターンと書き直しの型。
- `references/inspection/readability-principles.md`：語順、読点、一文一義、主語述語の距離など、機械閾値化できない読みやすさの一般原則。
- `references/inspection/readability-antipatterns.md`：悪文パターンのカタログ。
- `references/inspection/genre-notes.md`：ジャンル（tech、business、essay、公用文）ごとの判断の重みづけと許容される逸脱。
- `references/inspection/revision.md`：判断台帳、読みやすさレビュー手順、スイープ改稿の罠、発散ガード、収束条件、自己点検ループ、作業ファイルの扱い。
- `references/inspection/diagnose.md`：診断モード（score）の算出式と出力形式。

読みやすさの修正で短さを目的関数にしません。
事実の保持と、主述や係り受けの確認を済ませたあとの同等候補間でだけ、タイブレーカーとして短さを使います。

</References>
