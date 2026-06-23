return {
	-- tools
	{
		"mason-org/mason.nvim",
		opts = function(_, opts)
			vim.list_extend(opts.ensure_installed, {
				"stylua",
				"selene",
				"luacheck",
				"shellcheck",
				"shfmt",
				"tailwindcss-language-server",
				"typescript-language-server",
				"css-lsp",
				"nomicfoundation-solidity-language-server",
			})
		end,
	},

	-- lsp servers
	{
		"neovim/nvim-lspconfig",
		opts = {
			inlay_hints = { enabled = false },
			---@type lspconfig.options
			servers = {
				cssls = {},
				-- Solidity: Nomic Foundation server only (solidity_ls_nomicfoundation).
				-- It's the Hardhat team's own LSP: detects Hardhat/Foundry projects,
				-- resolves the compiler from the project config, and provides both
				-- diagnostics (via solc) and completion/navigation (via slang).
				-- DISABLE solidity_ls (juanfranblanco/vscode-solidity-server): it's
				-- Hardhat-2 era and crashes on Hardhat 3 projects (downloads
				-- soljson-latest.js into the project root then dies loading it),
				-- and mason-lspconfig's automatic_enable would re-enable it if its
				-- package stays installed. `enabled = false` keeps it out of
				-- ensure_installed and the automatic_enable exclude list.
				solidity_ls = { enabled = false },
				solidity_ls_nomicfoundation = {},
				-- NOTE: do not override root_dir here. LazyVim 16 configures
				-- servers via the native vim.lsp.config API where root_dir is
				-- async (bufnr, on_dir) — old lspconfig-style overrides keep
				-- the client suspended forever. The upstream default already
				-- detects tailwind.config.*/postcss.config.*/package.json
				-- tailwind deps, with .git as the v4 fallback.
				tailwindcss = {},
				-- TypeScript is handled by vtsls (lazyvim extras.lang.typescript).
				html = {},
				yamlls = {
					settings = {
						yaml = {
							keyOrdering = false,
						},
					},
				},
				lua_ls = {
					-- enabled = false,
					single_file_support = true,
					settings = {
						Lua = {
							workspace = {
								checkThirdParty = false,
							},
							completion = {
								workspaceWord = true,
								callSnippet = "Both",
							},
							misc = {
								parameters = {
									-- "-log-level=trace",
								},
							},
							hint = {
								enable = true,
								setType = false,
								paramType = true,
								paramName = "Disable",
								semicolon = "Disable",
								arrayIndex = "Disable",
							},
							doc = {
								privateName = { "^_" },
							},
							type = {
								castNumberToInteger = true,
							},
							diagnostics = {
								disable = { "incomplete-signature-doc", "trailing-space" },
								-- enable = false,
								groupSeverity = {
									strong = "Warning",
									strict = "Warning",
								},
								groupFileStatus = {
									["ambiguity"] = "Opened",
									["await"] = "Opened",
									["codestyle"] = "None",
									["duplicate"] = "Opened",
									["global"] = "Opened",
									["luadoc"] = "Opened",
									["redefined"] = "Opened",
									["strict"] = "Opened",
									["strong"] = "Opened",
									["type-check"] = "Opened",
									["unbalanced"] = "Opened",
									["unused"] = "Opened",
								},
								unusedLocalExclude = { "_*" },
							},
							format = {
								enable = false,
								defaultConfig = {
									indent_style = "space",
									indent_size = "2",
									continuation_indent_size = "2",
								},
							},
						},
					},
				},
			},
			setup = {},
		},
	},
	{
		"neovim/nvim-lspconfig",
		opts = {
			servers = {
				-- '*' applies to all LSP servers (LazyVim convention)
				["*"] = {
					keys = {
						{
							"gd",
							function()
								-- DO NOT REUSE WINDOW
								require("telescope.builtin").lsp_definitions({ reuse_win = false })
							end,
							desc = "Goto Definition",
							has = "definition",
						},
					},
				},
			},
		},
	},
}
