# Homebrew dependencies for this dotfiles repo.
# Apply with: ./install.sh --deps   (or: brew bundle --file="$HOME/.config/Brewfile")
#
# Curated on purpose: only tools the configs in this repo actually reference.
# Project-specific build deps do not belong here.

tap "anomalyco/tap"

# --- CLI core ---
brew "neovim"
brew "tmux"
brew "lazygit"
brew "fzf"
brew "fd"
brew "ripgrep"
brew "gh"
brew "ghq"
brew "jq"
brew "age"     # encrypt secret exports — see zsh/functions/secret.zsh
brew "git-flow"
brew "tree-sitter-cli"
brew "lynx"
brew "pngpaste"
brew "luarocks"
brew "libyaml" # ruby build dep (mise compiles ruby from source)
brew "mise"    # language runtimes + global npm CLIs — see mise/config.toml
brew "anomalyco/tap/opencode"

# --- Hermes Agent: audio / voice deps (CLI voice, TTS, Discord voice) ---
brew "ffmpeg"    # audio conversion for TTS / voice (all platforms)
brew "portaudio" # CLI voice mode: microphone input + playback (sounddevice)
brew "opus"      # Discord voice channel codec

# --- Hermes Agent: contextual-image-gen skill (image / SVG tooling) ---
brew "imagemagick" # magick/convert: resize, crop, .ico, composite, format convert
brew "webp"        # cwebp: WebP encoding for size-capped exports
brew "librsvg"     # rsvg-convert: high-quality SVG raster (+ ImageMagick SVG delegate)

# --- GUI apps / fonts (casks land in /Applications, shared across users) ---
cask "font-hack-nerd-font"
cask "font-geist"      # brand font for contextual-image-gen text/OG overlays
cask "font-geist-mono"
cask "ghostty"
cask "claude"    # Claude Desktop (Claude Code CLI is installed separately, see README)
cask "codex"              # Codex CLI
cask "codex-app"          # Codex desktop app
cask "copilot-cli"        # GitHub Copilot CLI
cask "github-copilot-app" # GitHub Copilot desktop app
