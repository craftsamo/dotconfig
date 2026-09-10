# Japanese Writing Usage Cases

Run requests in fresh contexts against no skill, the prior core and the new
core, using the same model/settings. Give the executor only a request and
the selected skill, not the expected observations below. Review anonymous
outputs for meaning, correctness, unnecessary edits and the requested style.
These cases are regression evidence, not a 0-100 naturalness score.

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

File delivery, source verification and review execution belong to the host
workflow and must not be fabricated by a read-only language trial.
