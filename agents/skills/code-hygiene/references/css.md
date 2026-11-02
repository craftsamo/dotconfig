# CSS, SCSS, Tailwind

Read with `SKILL.md`; the repository's design tokens, Tailwind theme,
Stylelint and Prettier configuration win over everything here.

## Values

- Search the existing tokens first: CSS custom properties, SCSS variables and
  maps, the Tailwind theme. Equal values are not enough: replace a raw value
  with a token only when the token means the same thing (a brand color for a
  brand color, not a spacing token for a line height that happens to share
  its pixels) and resolves to the same value everywhere the rule applies.
- A custom property resolves at the element. Before replacing, search for
  scopes that redefine it (theme classes, `[data-theme]`, density modifiers
  such as `.compact`, media queries) and for where the element is rendered;
  when the rule can apply inside such a scope, or that cannot be settled,
  leave the raw value and report it. Fallbacks in `var(--x, fallback)` must
  resolve the same as well.
- A raw value that repeats with the same meaning and has no token gets a
  custom property or SCSS variable in the file's or feature's existing
  variables location. Do not invent a new scale (spacing, color, z-index)
  where the project has none; report the missing scale instead.
- `z-index`, breakpoints and durations are the usual scattered values; give
  them names in one place when the project already keeps such names, and
  report them otherwise.

## SCSS

- Shared variables, mixins and functions live in partials (`_name.scss`)
  following the existing layout.
- Keep the module system the file already uses. Switching `@import` to `@use`
  changes scoping and load order: tier B.
- Flatten nesting only when the compiled selectors stay identical.
- Document mixins and functions with SassDoc (`///`) when the repository
  already does; plain section comments stay `/* */` or `//`.

## Tailwind

- An arbitrary value (`w-[13px]`, `text-[#1a1a1a]`) becomes a theme utility
  only when the theme has the exact value.
- A class string repeated across markup is reduced by extracting a component
  or a shared variant definition (`cva`, `tailwind-variants`) where the
  repository uses one; use `@apply` only if the repository already does.
- Class names must stay statically visible: never build them by string
  interpolation (`bg-${color}-500`), which the compiler cannot detect.
- Class order follows `prettier-plugin-tailwindcss` when it is configured;
  otherwise leave the order alone.
- Conditional classes use the repository's helper (`cn`, `clsx`).

## Files

- Tier A: moving variables or mixins into an existing partial; extracting a
  partial beside the file that uses it.
- Tier B: moving rules between stylesheets, changing which file imports
  which, switching between global CSS and CSS Modules.
- Tier C: global entry stylesheets imported by the framework, the Tailwind
  config's `content` globs, theme files consumed by tooling.

## Behavior traps

- Moving or reordering rules changes the cascade even when selectors are
  unchanged.
- Merging selectors changes specificity. Folding two rules with the same
  selector into one moves declarations across the rules between them, in
  either direction; fold only when no rule between them sets the same
  property on an element the folded selector can match.
- Renaming a class in CSS Modules or global CSS breaks markup and tests that
  reference it.
