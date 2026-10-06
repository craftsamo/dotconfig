return {
	{
		"stevearc/conform.nvim",
		opts = function(_, opts)
			opts.formatters_by_ft = opts.formatters_by_ft or {}
			opts.formatters = opts.formatters or {}

			opts.formatters_by_ft.markdown = { "prettier_markdown" }
			opts.formatters_by_ft["markdown.mdx"] = { "prettier_markdown" }
			-- A file reached through a symlink (the Hermes and private overlays)
			-- belongs to the repo it really lives in, so the ignore lookup and the
			-- path Prettier matches against it both use the resolved location.
			local function real(ctx)
				return vim.uv.fs_realpath(ctx.filename) or ctx.filename
			end
			opts.formatters.prettier_markdown = {
				inherit = "prettier",
				-- Prettier reads .prettierignore only from its working directory, and
				-- conform starts it next to a Prettier config, which most repos lack.
				cwd = function(self, ctx)
					return vim.fs.root(vim.fs.dirname(real(ctx)), ".prettierignore")
						or require("conform.formatters.prettier").cwd(self, ctx)
				end,
				args = function(_, ctx)
					return { "--stdin-filepath", real(ctx) }
				end,
			}
		end,
	},
}
