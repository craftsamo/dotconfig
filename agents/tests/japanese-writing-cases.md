# Japanese Writing Usage Cases

Run requests in fresh contexts against no skill, the prior core and the new
core, using the same model/settings. Give the executor only a request and
the selected skill, not the expected observations below. Review anonymous
outputs for meaning, correctness, unnecessary edits and the requested style.
These cases are regression evidence; they do not replace the skill's own
diagnosis or final review.

| Case | Request | Review observations |
| --- | --- | --- |
| Preserve natural compounds | 次の文を、不自然な箇所がなければそのまま残してください。「変更内容を確認します。環境変数で保存先を指定できます。」 | No obligatory expansion of 変更内容 or 環境変数. |
| Preserve qualification | 「実施できないわけではありません」を、留保の意味を変えずに見直してください。 | Must not strengthen to unqualified 実施できます. |
| Ambiguous modifier | 「新しい担当者の手順書を確認しました」の曖昧さを説明してください。 | Identifies both attachments; no arbitrary choice or rewritten-only answer. |
| Correct predicate | 目的は待ち時間の短縮です。「目的は、待ち時間を減らします」の主述の対応を直してください。 | Predicate identifies the purpose; no new reason or claimed result. |
| Draft from facts | 「保存先を選択可能になった」「既定の保存先は従来どおり」の2点だけを、落ち着いた日本語で案内してください。 | Both facts retained; no speed claim, dates, CTA or invented experience. |
| Respect house exceptions | この文書では「サーバ」を使います。「サーバの設定を確認します」を校正してください。 | Does not force サーバー as a universal rule. |
| Preserve natural nominal forms | 「処理の自動化について、具体的な方法を説明します」を、問題がなければそのまま残してください。 | Does not prohibit 自動化 or 具体的. |
| Scope near miss | 雑談です。今日は何を話そうか。 | Ordinary conversation does not require this deliverable skill. |
| Preserve an explained metaphor | 「エラー通知がないまま一部の記録が欠けます。このように静かに壊れるケースを調べます」を、問題がなければ残してください。 | Does not prohibit 静かに壊れる after its referent is supplied. |
| Unknown effect | 「この設定は地味に効きます」を、何が伝わりにくいか分析してください。設定の詳細は不明です。 | Identifies unspecified effect without inventing latency, error reduction or other results. |
| Tool candidate is not a correction | 検査で「できないわけではありません」が二重否定として挙がりました。誤りだけを校正してください。 | Preserves the reservation; does not turn the candidate into an affirmative or claim an error. |
| Useful list | 手順を「1. 保存先を選ぶ。2. 保存を実行する。」と列挙しています。箇条書き率が高いというだけで直す必要はありますか。 | Retains a useful ordered list; no ratio-derived quality verdict. |
| Missing machine evidence | 記事の機械検査が必須ですが、結果は partial で形態素解析が未実行です。完了状況だけ報告してください。 | Names the unverified checks, no zero-findings pass, automatic install or fabricated execution. |
| Diagnosis only | 次の記事を採点してください。書き換えは不要です。(AI っぽい定型句の多い 1,500 字程度の記事を添付) | Reports score, band, counts and up to 5 locations; no rewritten text; no claim about who wrote it. |
| No score without morphology | 形態素解析が使えない環境で「この文章を採点して」と依頼する。 | Withholds the number, names the unverified rules, gives qualitative findings only. |
| AI-like edit report | 「結論として、この施策は非常に重要と言えるでしょう。」を含む段落を自然にしてください。 | Removes stock phrasing without adding facts; report lists 変えたところ / 残した表現 / 確かめたい点. |
| Microsoft notation default | 「Gitの履歴を3つの観点（速度・容量）で確認します。」の表記を整えてください。 | 「Git の履歴を 3 つの観点 (速度、容量) で確認します。」 or equivalent half-width forms. |
| Existing unspaced convention | 全体が「Gitの履歴」のようにスペースなしで統一された文書の 1 段落を校正してください。 | Keeps the document's unspaced convention; does not force N1 spacing. |
| Doctype minutes | 次の文字起こしから議事録を作ってください。(決定 2 件、宿題 3 件を含む文字起こし) | Decisions findable on their own; tasks with owner, deadline and action; no invented owners or dates. |
| i18n near miss | `ja.json` の翻訳キーを整理して。 | Translation-file tooling is out of scope for the writing workflow. |

File delivery, source verification and review execution belong to the host
workflow and must not be fabricated by a read-only language trial.
