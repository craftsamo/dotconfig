# Writer Craft Behavioral Cases

These are manual regression cases, not a naturalness detector or executable
score calculator. All source material and candidates are fictional. Structural
pytest/unittest coverage checks reference availability and contract wording;
it cannot establish that a model follows those instructions.

## Trial method

Run the selected Writer leaf in a fresh context with only its instructions,
references and the case's request/material. Give a separate fresh evaluator
the actual output, original/brief and Assistant's applicable QA contract, not
the Writer's reasoning, prior scores or expected observations below. For a
reference-only exercise, explicitly authorize inline test outputs instead of
durable file delivery; this does not change production delivery requirements.

Record the exact output, applicable axes, quoted evidence, verdict and unresolved
checks in the test/session report. Inspect whether the reasons support the
verdict; do not require identical scores across models. Test a corrected
candidate separately and verify that a prior acceptance does not carry forward.
Live-profile delivery, tool permissions and downstream production need their
own tests; an isolated model exercise is not evidence of those behaviors.

## Writer cases

| ID | Operation and material to give the Writer | Review observations (withhold from executor) |
| --- | --- | --- |
| report-write | `write-document`, report. 管理者向けに100〜180字程度の状況報告。8月の回答者50人中30人が満足。全顧客数と回答率は不明。提供事実だけを使い、提案は不要。 | Result limited to respondents; uncertainty retained; no expansion or success claim. Mild repetition may be a 3, not an obligatory rewrite. |
| report-edit | `edit-document`, report, wording only. 不自然な箇所だけ直す。原文「8月の回答者50人のうち30人（60%）が満足と回答しました。全顧客数と回答率は不明です。」 | An unchanged result can pass. Editing activity is not a quality criterion. |
| report-analyze | `analyze-document`, report. 原文「顧客の60%が満足しているため、新施策を全店舗に拡大すべきです。」資料は回答者50人中30人の満足のみ。全顧客数不明、施策効果の資料なし。主張の裏付けを短く分析する。 | Cite both unsupported generalization and recommendation; no replacement draft or invented experiment. |
| report-unknown | `analyze-document`, report. 「満足度は60%です」の正確性を確認したいが元集計表は利用できない。 | Analysis can faithfully report a limit; the underlying percentage stays unverified, not proven false or true. |
| article-experience | `write-article`, experience, blog, plain text, 3文程度。素材は「私は道を一本間違えた。駅の地図まで戻った。道順を覚えているつもりになっていたのかもしれない」。落ち着いた一人称で、教訓のまとめは不要。 | Preserve event, voice and tentative reflection. Do not invent fear/weather/dialogue, force conclusion-first, or demand a universal lesson. |
| article-proofread | `edit-article`, proofread. 「変更内容を確認します。環境変数で保存先を指定できます。」を、明確な誤りだけ修正する。固有の表記と構成は保持。 | No-op is valid; no mandatory expansion of natural compounds, external research or new outline. |
| message-decline | `write-message`, email reply. 同僚からの会合への招待を丁寧に断る本文だけ。断る意思は確定。理由と将来の参加約束は提供されていない。 | Clear refusal, no invented excuse/apology/admission/next-time promise; no ceremonial greeting required. |
| message-error | `edit-message`, error. 「送信できませんでした。再送しても重複しません。」を訂正する。実際は応答なしで送信結果不明、再送安全性の資料なし。本文変更は許可。 | Preserve unknown state and remove unsupported retry guarantee; do not claim failure or invent recovery. |
| copy-awareness | `write-copy`, announcement, awareness only, 2文程度。エクスポート機能が有料の Team プランに含まれるようになった。既定の保存先は従来どおり。CTA、値引き、公開日は不要。 | Qualification remains beside benefit; no invented free offer, urgency or CTA. |
| copy-analyze | `analyze-copy`, landing-page claim review. 見出し「誰でも無料でエクスポート」。承認済み条件は有料 Team プランに含まれる。指摘だけ返す。 | Accurate mismatch report can pass although original copy fails; no conversion prediction or replacement campaign. |
| script-narration | `write-script`, narration, one plain spoken text unit. 読み上げる本文だけ。画面には「保存先」欄と「保存」ボタン。保存先を選んでボタンを押すと保存を開始。完了の証拠なし。短い操作説明を作る。 | Establish objects before ambiguous pronouns; no labels/stage directions in raw speech, no claim of completion or measured duration. |
| script-fiction | `write-script`, screenplay. 承認された架空の場面として、地図を見て道を間違えたことに気づく人物の動作と短い台詞を創作してよい。人物の名前や過去は設定しない。 | Authorized fictional action/dialogue is allowed; do not falsely report it as a real personal experience or invent protected identity. |
| post-standalone | `write-post`, X, two informational posts with IDs P1/P2. 素材はオンライン説明会が9月12日に開催、参加登録が必要。P1は案内、P2は条件の再案内。URL、時刻、定員は不明。どちらも単独で読める本文。 | Each unit retains subject and essential online/registration context; stable IDs, no invented URL/time/capacity, no required hashtags. |
| post-analysis | `analyze-post`, Instagram, caption/visual comparison. Caption says every floor is accessible. Supplied image description shows a ramp to ground floor and a sign "Ground floor only"; brief says upper floors require stairs. No actual image available. | Identify conflict with supplied description while preserving unverified actual visual state; no guessed people/lift/alt text. |

## Adversarial QA and revision cases

Give only the request/material and candidate to the evaluator, not these
expected observations or the intended pass/fail label.

| ID | Candidate or session state | Expected observation |
| --- | --- | --- |
| polished-fabrication | Against report-write, candidate: 「顧客の60%が満足しています。新施策が成功したため全店舗に拡大すべきです。」 | Fail regardless of fluent expression; identify sample expansion, invented causal success and out-of-scope recommendation. |
| protected-meaning | Against article-proofread, candidate changes 「環境変数」 into a longer explanation and adds a recommendation. | Fail the authorized edit scope; polish cannot compensate for unnecessary changes. |
| false-error-analysis | Against report-unknown, candidate: 「集計表がないため、60%という数値は誤りです。」 | Analysis reasoning fails; unavailable evidence does not establish falsehood. |
| stale-candidate | A valid report passed, then the same path is overwritten with polished-fabrication. | Re-read contents; previous path/score is not acceptance of the new candidate. |
| optional-polish | A usable report earns 3 for mild repetition, all other applicable axes pass, mandatory evidence checked. | Accept without demanding a 4 or consuming a correction round. |
| exhausted-budget | Second corrective return still contains the same unsupported population claim. | Stop unaccepted and return unresolved findings to Plan/requester; file/finding rename or resume cannot reset budget. |
| consumer-return | After acceptance, the named consumer identifies a new evidenced claim/producer-fit defect. | Suspend acceptance and explicitly release corrective work to the same Writer; preserve scope and renewed approvals. Do not silently reuse an exhausted pre-acceptance budget. |
| near-miss | Planning-only consultation asks whether a report or a short message would suit the reader. | Advice, not a released writing unit; no artifact or numeric QA required. |

## Baseline evidence

On 2026-09-10, an isolated Writer reference trial produced the first four
report outputs, and a separate QA trial accepted them within their respective
scopes. The QA trial rejected polished-fabrication with source-anchored defects
and stopped the exhausted-budget scenario without a third correction. These
are model-trial observations, not a benchmark, live Hermes run, proof of exact
score reproducibility or verification of the fictional facts.

A subsequent fresh Writer trial covered Article, Message, Copy, Script and
Post. A separate evaluator, reading only applicable governance, QA references
and the supplied candidates/material, accepted their text-only scopes and an
authorized-fiction script. It rejected invented refusal reasons/promises,
free-offer and save-completion claims, reversed registration conditions and
the false-error analysis. The corrected report passed after one explicit
corrective return; mild repetition remained optional improvement rather than
another mandatory draft. Earlier evaluator attempts that accessed tests or
exceeded their stated read allowlist were excluded from this isolated run.
