# Editing Blog Drafts

Preserve the existing engine's syntax and metadata. A source edit must not
silently change slugs, redirects, asset URLs, code blocks or custom shortcodes.
Unknown rendering behavior stays unverified rather than being normalized to
the editor's preferred Markdown dialect.

Changing destination is a format migration requiring explicit scope. Identify
unsupported features and propose replacements without discarding their meaning.
Keep production notes and unresolved asset IDs separate from publishable text.
No CMS configuration, plugin installation, deployment or live edit is authorized.
