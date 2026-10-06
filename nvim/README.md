# Neovim

[LazyVim](https://www.lazyvim.org/)-based configuration. Plugins are managed
by lazy.nvim and pinned in `lazy-lock.json`; LazyVim extras are declared in
`lazyvim.json` (`ai.copilot`, `lang.yaml`, `util.octo`).

## Layout

```
nvim/
├── init.lua          # enables vim.loader, defines the dd() debug helper, boots config.lazy
├── lazy-lock.json    # pinned plugin versions (committed on purpose)
├── lazyvim.json      # LazyVim extras
└── lua/
    ├── config/       # lazy.nvim bootstrap, options, keymaps, autocmds
    ├── plugins/      # one spec file per plugin (additions and overrides)
    ├── craftsamo/    # personal helper modules (see below)
    └── util/         # debug helpers (dd / vim.print)
```

## Personal modules (`lua/craftsamo/`)

| Module           | Purpose                                                                     |
| ---------------- | --------------------------------------------------------------------------- |
| `discipline.lua` | "Hold it Cowboy!" — warns when `h/j/k/l/+/-` is mashed >10x in 2s           |
| `hsl.lua`        | `<leader>r` replaces the hex colour under the cursor with HSL               |
| `lsp.lua`        | `<leader>i` toggles inlay hints; `:ToggleAutoformat` toggles format-on-save |

## Notable keymaps (`lua/config/keymaps.lua`)

- Register-safe editing: `x`, `<Leader>c/C`, `<Leader>d/D` use the black-hole
  register; `<Leader>p/P` paste from yank register `0`
- `+` / `-` increment / decrement, `dw` deletes a word backwards,
  `<C-a>` selects the whole buffer
- Tabs and splits: `te` new tab, `<tab>` / `<s-tab>` cycle tabs,
  `ss` / `sv` split, `s` + `h/j/k/l` move between windows,
  `<C-w>` + arrows resize
- `<C-j>` jumps to the next diagnostic

## Requirements

Everything is installed by the repo [Brewfile](../Brewfile): `neovim`,
`ripgrep`, `fd`, `fzf`, `lazygit`, `tree-sitter-cli`, `luarocks`, `pngpaste`
(image paste on macOS). Node.js — required by Copilot and several LSP
servers — is managed via [mise](../mise/config.toml) (`node = "lts"`) and
installed by `./install.sh --deps`.
