local media_patch = vim.fn.shellescape(vim.fn.stdpath("config") .. "/patches/markdown-preview-local-media.patch")

return {
	{
		"iamcco/markdown-preview.nvim",
		cmd = { "MarkdownPreview", "MarkdownPreviewStop", "MarkdownPreviewToggle" },
		ft = { "markdown" },
		pin = true,
		build = "yarn --cwd app install && (git apply --unidiff-zero --reverse --check "
			.. media_patch
			.. " >/dev/null 2>&1 || git apply --unidiff-zero "
			.. media_patch
			.. ")",
		keys = {
			{ "<leader>mp", "<cmd>MarkdownPreviewToggle<cr>", desc = "Markdown Preview" },
		},
	},
}
