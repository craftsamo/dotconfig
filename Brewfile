# Homebrew dependencies for this dotconfig repo.
# Apply with: ./install.sh --deps   (or: brew bundle --file="$HOME/.config/Brewfile")
#
# Curated on purpose: only tools the configs in this repo actually reference,
# plus system binaries required by the skills those configs load (Hermes
# external skill dirs, shared ~/.agents/skills). Project-specific build deps
# do not belong here.

tap "anomalyco/tap"
tap "openclaw/tap"
tap "steipete/tap"
tap "xdevplatform/tap"

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
brew "ghostscript" # gs — nvim snacks: render PDF/LaTeX as inline images
brew "lynx"
brew "pngpaste"
brew "luarocks"
brew "libyaml" # ruby build dep (mise compiles ruby from source)
brew "mise"    # language runtimes + global npm CLIs — see mise/config.toml
brew "uv"      # python venv/deps manager — required by hermes/setup.sh
brew "anomalyco/tap/opencode"
brew "foundry"  # forge/anvil/cast — Solidity LSP (forge_fmt) + Foundry toolchain
brew "solidity" # solc — Solidity compiler CLI (ad-hoc compile; Nomic LSP resolves solc via Hardhat)

# --- Hermes Agent: audio / voice deps (CLI voice, TTS, Discord voice) ---
brew "ffmpeg"    # audio conversion for TTS / voice (all platforms)
brew "portaudio" # CLI voice mode: microphone input + playback (sounddevice)
brew "opus"      # Discord voice channel codec

# --- Hermes Agent: contextual-image-gen skill (image / SVG tooling) ---
brew "imagemagick" # magick/convert: resize, crop, .ico, composite, format convert
brew "webp"        # cwebp: WebP encoding for size-capped exports
brew "librsvg"     # rsvg-convert: high-quality SVG raster (+ ImageMagick SVG delegate)

# --- Hermes Agent: whatsapp-access plugin (see hermes/docs/whatsapp-access.md) ---
brew "openclaw/tap/wacli" # WhatsApp linked-device CLI: local mirror + send

# --- Hermes Agent: signal-access plugin (see hermes/docs/signal-access.md) ---
brew "signal-cli"  # Signal linked-device CLI (native build): sync agent + send

# --- Hermes Agent: Assistant tools ---
cask "gcloud-cli"              # gcloud — google-access plugin + bin/gaccess
brew "deno"                    # youtube-access plugin: yt-dlp's YouTube challenge solver
brew "steipete/tap/remindctl"  # apple-reminders skill (hermes-agent skills/apple)
cask "xdevplatform/tap/xurl"   # xurl skill (hermes-agent skills/social-media)

# --- Hermes Agent: video-creator tour (OCR text anchors) ---
brew "tesseract"      # tour.py locates targets by OCR
brew "tesseract-lang" # jpn traineddata for jpn / eng+jpn anchors

# --- Shared skills (~/.agents/skills: hyperframes, media-use, business-video-maker) ---
brew "whisper.cpp" # whisper-cli — transcription / captions
brew "espeak-ng"   # Kokoro TTS phonemizer for non-English + fallback narration

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
cask "brave-browser"  # Hermes real-profile browsing clones it — see hermes/scripts/brave-agent-sync.sh
cask "google-chrome"  # creator brand-asset-sourcing scripts hardcode its path
cask "docker-desktop" # docker CLI (~/.docker/bin) wrapped by bin/secret-shim
cask "tailscale-app"  # `tailscale serve` exposes the OpenCode web server — see tmux/README.md
# NOTE: Grok Build CLI (xAI) is NOT installed via the grok-build cask: binaries under
# /opt/homebrew/Caskroom hang in dyld on this machine. Installed via the official
# installer instead (see grok/README.md), like Claude Code CLI.
