# JavaScript, JSX, TypeScript, TSX

Read with `SKILL.md`; the repository's `tsconfig`, ESLint and Prettier
configuration win over everything here.

## Types

- Search before declaring. A shape that already exists as a type, a schema
  (`z.infer<typeof Schema>`), a generated client type or a library export is
  reused, not restated.
- Derive instead of copying: `Pick`, `Omit`, `Partial`, `Required`,
  `ReturnType`, `Parameters`, `Awaited`, `typeof value`, `keyof`, indexed
  access (`User["id"]`).
- An inline object type that appears twice becomes one named type in the
  narrowest home: the top of the file, a sibling `*.types.ts` (or whatever
  sibling name the repository uses), then the repository's shared types
  module.
- Derive unions from a single source:
  `const ROLES = ["admin", "member"] as const; type Role = (typeof ROLES)[number];`
- Use `satisfies` to check a literal against a type without widening it.
- Follow the repository on `type` vs `interface` and on `enum` vs literal
  unions; do not introduce `enum` into a codebase that uses unions.
- Replace `any` with the real type when it is known and the typecheck proves
  it; otherwise leave it rather than inventing one. On an exported
  declaration this changes what consumers see: tier B. Replacing an inline
  shape in an exported signature with the named type it restates (the
  feature's own type for the same data, not a coincidental match) keeps the
  structure and is tier A. Type-only imports use `import type`.

## Constants

- Module-level `UPPER_SNAKE_CASE` (or the repository's casing) with
  `as const` for literals whose exact value matters to types.
- Related strings become one object map or `as const` array instead of
  repeated literals: event names, route keys, storage keys, status values.
- Configuration that differs per environment is not a constant; leave it
  where the repository reads configuration.

## Doc comments

- A `//` comment directly above a function, class, type, interface, exported
  constant or React component becomes `/** ... */`.
- Keep the content; restructure it into TSDoc tags only where the content
  already says it: `@param`, `@returns`, `@throws`, `@example`,
  `@deprecated`, `@see`.
- In plain JavaScript, use JSDoc types the repository already relies on
  (`@param {string} id`, `@typedef`) so editors and `checkJs` keep working.
- Comments inside function bodies stay `//`.

## React and JSX

- Props type named `<Component>Props`, declared next to the component unless
  the repository keeps them elsewhere.
- One exported component per file. Small private subcomponents used only by
  that file may stay.
- Constants that do not depend on props or state may move above the
  component, except when the value flows into a dependency array, `memo`,
  `useMemo`/`useCallback` deps or a context value: hoisting changes its
  identity and therefore when effects and renders run. Leave those.
- Hooks extracted into a sibling `useX.ts` keep their call order and
  conditions.

## Files and directories

- Tier A: siblings such as `foo.types.ts`, `foo.constants.ts`, `useFoo.ts`,
  `foo.utils.ts`, following the names already used in the directory.
- Tier B: barrels (`index.ts`), moving between feature folders, renaming
  files, changing exported names.
- Tier C: `app/`, `pages/`, `routes/` and other file-based routing trees,
  `middleware`, framework convention files (`layout`, `page`, `loader`,
  `+page`), `package.json` `main`/`exports`, files named in build or test
  configuration.
- A new file is picked up by name, so check it before creating it: a name
  ending in `.test.ts`, `.spec.ts` or placed under `__tests__/` usually
  becomes a test (read the runner's include pattern); it must stay inside
  `tsconfig` `include` and `package.json` `files`; a file with import-time
  side effects must match `package.json` `sideEffects` when that field is a
  list; reserved names (`page`, `layout`, `route`, `+page`) and auto-import
  directories (Nuxt `composables/`, `utils/`) turn a helper into a route or a
  global. Tailwind class strings follow `css.md`.

## Behavior traps

- `||` and `??` differ for `0`, `""` and `false`; optional chaining differs
  from an explicit check that throws.
- `function` declarations hoist and bind `this`; arrow functions do neither.
- A private method or property reached through a computed key
  (`this["on_" + status]`) or a string-keyed registry has no direct caller
  but is not dead code, and renaming it breaks the lookup.
- Reordering imports can reorder module side effects (polyfills, CSS,
  registration calls).
- `as const` and `satisfies` change inferred types; the typecheck must still
  pass across importers.
- Converting `export default` to a named export, or the reverse, is a public
  API change (tier B).
