# note: text-article drafts

## Scope and planning

Initial target: a text article in the named account's web editor. Paid settings,
magazines, membership, external distribution and new accounts are separate work.
Writer owns article words and production notes. Do not promise Markdown import,
HTML support or an embed merely because the source contains it.

## Browser procedure

Follow [draft](../../build-marketer/references/draft.md). Confirm the account and existing target before
entry. Approve new-draft creation BEFORE opening a new editor: it can allocate
a service-side draft identity without any text. note also autosaves while editing;
obtain exact input/upload consent, not just permission for a final save button.

Inspect the current draft-save control and saving state. Enter the approved
article and supported media; preserve paragraphs, links, quotations and captions.
The observed editor is on editor.note.com, separate from note.com's article
view. Wait for its fields after navigation; an initially empty DOM is not a
missing editor. Retain the assigned article identity rather than reopening New.
The presence of a textarea alone also does not prove hydration is complete:
the tested reopen briefly exposed an empty title before action controls appeared.
Wait boundedly for the current editor's content and controls to settle, then
re-read the same draft. Do not resave or recreate it to repair a loading-state
read. After readiness, an actual content mismatch still stops the operation;
never poll until a changed manuscript happens to match the expected text.

For the observed ProseMirror body, prefer native character key events and named
Enter key events over one multiline Input.insertText. The latter lost text in
the smoke trial; type_text is the same low-level insertion, not a fallback.
One Enter produced a line break, the next a new paragraph in that trial. Inspect
actual paragraph blocks/rendering, never assume newline count or hardcode that
key count for every future UI. Restore only the approved contents of the known
test/work draft after reconciling any failed input; never change words or another
draft. Do not assign editor internals or DOM text as a substitute for normal input.

Wait for saving to finish and use explicit draft save when the current editor
offers it. Do not navigate forward to publication settings as a save shortcut.
Session/network loss can leave saving incomplete: report it rather than closing
the editor and assuming success.

A save/close flow may show a completion dialog over the editor. Inspect the
actual overlay; scope its Close control to that dialog rather than clicking the
underlying editor's identically named control. In the observed flow, dismissal
led to an authenticated article view explicitly labeled unpublished; its Edit
control reopened the same service draft. Do not confuse a public-shaped article
URL with publication or generate a sharing link to reach this view.

## Verification and measurement

Reopen the same article from the service's article/draft management surface and
apply [saved-draft QA](../../qa-marketer/references/saved-draft.md). Confirm unpublished
status, no scheduling and no changed paid/access settings. Do not generate the
separate sharing-preview link. A future public URL is not proof of publication
or proof that this draft is privately accessible to the client.

Read permitted dashboard/public observations with definitions and periods. Do
not infer completion rate, unique continuing readers or sales from likes alone.
No export/sharing/account changes as part of collecting counts.

## Sources and status

- [Save/reopen drafts](https://www.help-note.com/hc/ja/articles/360009035633)
- [Autosave](https://www.help-note.com/hc/ja/articles/360012426133)
- [Sharing preview](https://www.help-note.com/hc/ja/articles/360018997193)
- [Terms](https://terms.help-note.com/hc/ja/articles/44943817565465)

Reviewed 2026-09-10. One approved text-only native-backend smoke succeeded:
existing Marketer browser, new service draft, exact title/two paragraphs,
explicit save, unpublished-view banner, Edit/reopen and exact-content comparison.
Screenshots and identifiers remain in the private job record, not this skill.
This validates the bounded browser procedure, NOT a fresh candidate AIAgent
end-to-end run. Attachments, rich content, existing-user-draft updates, account
switching and other media remain unverified. Recheck UI before each operation.
No challenge bypass, unsolicited actions or account-credential transfer.

A separate fresh candidate AIAgent smoke on 2026-09-10 passed read-only rechecking:
kernel -> QA index -> saved-draft/platform references, lease acquisition, actual
editor/content and unpublished-banner observations, then lease release and report.
Its browser surface was limited to two exact read-only programs, not unrestricted
selector discovery or creation/update. Missing viewer-account metadata was
reported unverified rather than inferred from the article author. This does not
validate a deployed gateway, autonomous saving or the other untested scopes above.

On 2026-09-11, a fresh candidate AIAgent also performed one constrained unchanged
resave of that existing test draft. It read the homepage's current-account
indicator, compared the exact existing title/two paragraphs and unpublished
banner, invoked the sole allowed draft-save action once, observed confirmation,
then reopened/compared and released the lease. A transient empty loading-state
read led to another read, not another save. The harness provided fixed browser
programs; no text input, new draft, free-form editor operation or publication was
permitted. The original run's only failed harness check was serial ordering of
parallel reference reads; common indexes were present before browser work. The
contract now permits parallel reference loading without omitting common rules.
This is evidence for bounded existing-draft saving, not general editing support.
