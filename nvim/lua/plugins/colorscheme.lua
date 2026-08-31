return {
	{
		"craftzdog/solarized-osaka.nvim",
		lazy = true,
		priority = 1000,
		opts = function()
			-- Blend an accent color into the background (for dark UI shades)
			local function dim(color, amount)
				local background = "#0D1116"
				local function channel(hex, index)
					return tonumber(hex:sub(index, index + 1), 16)
				end
				local function blend(index)
					local value = amount * channel(color, index) + (1 - amount) * channel(background, index)
					return math.floor(math.min(math.max(0, value), 255) + 0.5)
				end

				return string.format("#%02x%02x%02x", blend(2), blend(4), blend(6))
			end
			return {
				transparent = true,
				on_colors = function(c)
					-- Background / foreground (Ghostty palette)
					c.bg = "#0D1116"
					c.bg_highlight = "#1a1f26"
					c.base04 = "#0D1116"
					c.base03 = "#1a1f26"
					c.fg = "#ffffff"

					-- Neutral grays (replace teal-tinted Solarized bases)
					c.base02 = "#222a38" -- Visual bg, Pmenu bg, UI borders
					c.base01 = "#5a6577" -- comments / dim text (matches tmux dim fg)
					c.base00 = "#7c8696" -- NormalNC fg, NonText
					c.base0 = "#a0a8b8" -- main text (matches tmux statusline fg)
					c.base1 = "#b6bfcc"
					c.base2 = "#e8edf5"

					-- Accent colors (main 500 only, matching Ghostty palette)
					c.magenta = "#fca6ff"
					c.magenta500 = "#fca6ff"
					c.violet = "#987afb"
					c.violet500 = "#987afb"
					c.blue = "#987afb"
					c.blue500 = "#987afb"
					c.green = "#37f499"
					c.green500 = "#37f499"
					c.yellow = "#9ad900"
					c.yellow500 = "#9ad900"
					c.cyan = "#04d1f9"
					c.cyan500 = "#04d1f9"
					c.red = "#f16c75"
					c.red500 = "#f16c75"
					c.orange = "#e58f2a"
					c.orange500 = "#e58f2a"

					-- Bright accent shades (fg accents used by treesitter/UI)
					c.cyan300 = "#67e0ff" -- @string.regexp
					c.yellow300 = "#b8e632" -- @variable.parameter.builtin
					c.blue300 = "#b4a4fc" -- MiniIconsAzure

					-- Mid shades (UI accents, derived from the neon 500s)
					c.yellow700 = dim(c.yellow500, 0.50) -- LineNr, FloatBorder
					c.violet700 = dim(c.violet500, 0.65) -- indent scope, HopNextKey2
					c.blue700 = dim(c.blue500, 0.30) -- QuickFixLine bg
					c.green700 = dim(c.green500, 0.30) -- markdown code delimiter bg
					c.orange700 = dim(c.orange500, 0.80) -- @string.escape

					-- Dark shades (diff / virtual-text backgrounds)
					c.green900 = dim(c.green500, 0.25) -- DiffText, Neogit add
					c.green950 = dim(c.green500, 0.10) -- DiffChange
					c.cyan900 = dim(c.cyan500, 0.18) -- DiffAdd, hint vtext bg
					c.red900 = dim(c.red500, 0.25) -- Neogit delete, error vtext bg
					c.red950 = dim(c.red500, 0.14) -- DiffDelete
					c.yellow900 = dim(c.yellow500, 0.22) -- warn vtext bg
					c.blue900 = dim(c.blue500, 0.22) -- info vtext bg
					c.magenta900 = dim(c.magenta500, 0.20) -- LspReference*
					c.violet900 = dim(c.violet500, 0.22) -- TreesitterContext, LspInlayHint

					-- Derived keys are snapshotted BEFORE on_colors runs
					-- (solarized-osaka/colors.lua calls on_colors last), so
					-- re-derive them here to drop stale Solarized values.
					c.error = c.red500
					c.warning = c.yellow500
					c.info = c.blue500
					c.hint = c.cyan500
					c.todo = c.violet500
					c.black = "#0a0e14"
					c.border = "#1a1f26"
					c.bg_popup = "#11161d"
					c.bg_float = "#11161d"
					c.bg_sidebar = "#0D1116"
					c.bg_statusline = "#11161d"
				end,
				on_highlights = function(hl, c)
					-- Diagnostic virtual text: drop the heavy background, keep only foreground
					hl.DiagnosticVirtualTextError = { fg = c.red500, bg = "NONE" }
					hl.DiagnosticVirtualTextWarn = { fg = c.yellow500, bg = "NONE" }
					hl.DiagnosticVirtualTextInfo = { fg = c.blue500, bg = "NONE" }
					hl.DiagnosticVirtualTextHint = { fg = c.cyan500, bg = "NONE" }

					-- MatchParen: subtle highlight instead of red wash
					hl.MatchParen = { fg = c.cyan500, bold = true, underline = true }

					-- LSP / Illuminated word references: dim instead of magenta wash
					hl.LspReferenceText = { bg = c.bg_highlight }
					hl.LspReferenceRead = { bg = c.bg_highlight }
					hl.LspReferenceWrite = { bg = c.bg_highlight }
					hl.IlluminatedWordRead = { bg = c.bg_highlight }
					hl.IlluminatedWordWrite = { bg = c.bg_highlight }

					-- nvim-treesitter main branch: new capture families the
					-- colorscheme does not cover yet
					hl["@keyword.modifier"] = { fg = c.green500, italic = true } -- rust const/pub, ts readonly/private
					hl["@keyword.type"] = { fg = c.green500, italic = true } -- class/interface/enum/namespace

					-- tsx parity: upstream defines @variable.typescript/.javascript
					-- (yellow) but not @variable.tsx, so identifiers in .tsx
					-- buffers fall back to the plain gray @variable
					hl["@variable.tsx"] = { fg = c.yellow500 }

					-- Markdown headings: per-level neon colors. render-markdown
					-- links H<n> fg to these captures; give H<n>Bg a matching
					-- dimmed background instead of the default Diff* links.
					local headings = { c.magenta500, c.violet500, c.cyan500, c.green500, c.yellow500, c.orange500 }
					for i, color in ipairs(headings) do
						hl["@markup.heading." .. i .. ".markdown"] = { fg = color, bold = true }
						hl["RenderMarkdownH" .. i .. "Bg"] = { bg = dim(color, 0.15) }
					end
				end,
			}
		end,
	},
}
