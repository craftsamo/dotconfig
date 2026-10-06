return {
	{
		"stevearc/conform.nvim",
		opts = function(_, opts)
			opts.formatters_by_ft = opts.formatters_by_ft or {}
			opts.formatters = opts.formatters or {}

			opts.formatters_by_ft.markdown = { "prettier_markdown" }
			opts.formatters_by_ft["markdown.mdx"] = { "prettier_markdown" }
			opts.formatters.prettier_markdown = {
				inherit = "prettier",
				-- Prettier reads .prettierignore only from its working directory, and
				-- conform starts it next to a Prettier config, which most repos lack.
				cwd = function(self, ctx)
					return vim.fs.root(ctx.dirname, ".prettierignore")
						or require("conform.formatters.prettier").cwd(self, ctx)
				end,
			}
		end,
	},
}
