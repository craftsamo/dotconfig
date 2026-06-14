return {
	{
		"nvim-treesitter/nvim-treesitter",
		-- NOTE: nvim-treesitter is on the `main` branch (rewrite). Parser
		-- installation and highlighting are handled by LazyVim's default
		-- config; a custom `config` here would override and break it.
		-- Master-only options (playground, query_linter, ...) were removed.
		opts = {
			ensure_installed = {
				"astro",
				"cmake",
				"cpp",
				"css",
				"fish",
				"gitignore",
				"go",
				"graphql",
				"http",
				"java",
				"latex",
				"php",
				"rust",
				"scss",
				"sql",
				"svelte",
			},
		},
		init = function()
			-- MDX
			vim.filetype.add({
				extension = {
					mdx = "mdx",
				},
			})
			vim.treesitter.language.register("markdown", "mdx")
		end,
	},
}
