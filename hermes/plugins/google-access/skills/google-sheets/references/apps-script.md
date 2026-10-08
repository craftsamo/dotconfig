# Apps Script exception

Use only when no `google_sheets` op can make the change (for example an image
inside a cell) and the user has agreed for this sheet. Tell the user first
what the tool lacks, and report it afterwards as a missing op.

1. **Write the data with the tool first** and settle tab names and columns.
   The script addresses columns by position, so a later column change means
   running it again.
2. **Write the script as a file** in the job directory: small,
   single-purpose and idempotent. Start its doc comment with
   `@OnlyCurrentDoc`, so the consent screen asks only for "this spreadsheet",
   never Drive-wide access.
3. **Open the bound editor** from the sheet (Extensions → Apps Script) in the
   user's own browser profile. Put the code in through the editor's model
   (`monaco.editor.getModels()[0].setValue(...)`) rather than typing it, and
   save.
4. **Run it.** The first run asks for authorization. Read the scope text
   before approving and continue only if it names the one spreadsheet;
   broader scopes mean the header is missing, so fix it and run again. Never
   type a password or code into the consent flow; if a login page appears,
   relaunch the browser (`hermes-browser-relaunch`) instead.
5. **Verify** with the tool: `get_format` for what was set, `snapshot` for
   how it looks, `get` for values.
6. **Clean up.** Close the editor and consent tabs. Tell the user that a
   script project stays bound to the sheet and which scope it holds. Delete
   it (script.google.com → the project whose "open spreadsheet" link has the
   sheet's id, never one picked by name → delete permanently) only after the
   user says so; deletion has no trash. What the script set stays in the
   sheet after the project is gone.
