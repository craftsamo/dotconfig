return {
	{
		"stevearc/conform.nvim",
		opts = function(_, opts)
			opts.formatters_by_ft = opts.formatters_by_ft or {}
			opts.formatters = opts.formatters or {}

			opts.formatters_by_ft.markdown = { "prettier_markdown" }
			opts.formatters_by_ft["markdown.mdx"] = { "prettier_markdown" }
			opts.formatters.prettier_markdown = { inherit = "prettier" }
		end,
	},
}
