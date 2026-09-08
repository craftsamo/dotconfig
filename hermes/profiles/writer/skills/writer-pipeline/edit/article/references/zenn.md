# Editing Zenn Source

Preserve existing fenced code, link destinations, image sources and article
metadata unless the requested change includes them. A prose edit does not
authorize changing code behavior or adding fabricated execution output.

Zenn accepts Markdown, including tables and documented extensions. Verify
any extension actually needed against the guide rather than assuming generic
HTML support. Moving a heading can invalidate internal links; check their
meaning and known anchors without claiming a rendered preview.

If the source is repository-managed, preserve its supplied frontmatter and
file conventions. If it is editor-bound, do not add an unrequested CLI layout.
Unresolved image/table/embed IDs remain production dependencies.

Documentary source (checked 2026-09-08; no preview test):
https://zenn.dev/zenn/articles/markdown-guide
