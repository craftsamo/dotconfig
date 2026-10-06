# A note save package from Marketer

A resident Marketer cannot save to note: nobody can answer its approval card
there, so the tool refuses. Marketer checks the save with `preview=true` and
returns a package instead:

- the action (`create_draft` or `update_draft`) and the account;
- for an update, the draft key and `base`;
- the title and the whole Markdown;
- absolute image and cover paths, each with the SHA-256 its preview gave;
- the card its preview showed, and its content-acceptance evidence.

You save it with your own card. No approval is relayed or inferred across
sessions: the card the user answers here is the consent.

1. **Preview it exactly as received.** Call the same action with the
   package's arguments, `base` included, plus `preview=true`. Its
   `files[].sha256`, `key`, `base` and `account` must equal the package's.
   On any difference or refusal (the draft was saved since, an image changed
   or moved, a path outside your attach roots) send the package back to the
   same Marketer conversation with the tool's answer. Do not fix it yourself,
   not even the markup.
2. **Agree the content.** Show the user the full Markdown, or the file it
   came from, and get their OK.
3. **Save.** The same call without `preview`, never with edited Markdown. Its
   card is the remote-save consent.
4. **Hand the result back.** Pass the tool's whole result to the same
   Marketer conversation, which re-reads the draft and records it. A denial
   ends the save; an `UNCERTAIN` result goes to Marketer to reconcile before
   anything else.
