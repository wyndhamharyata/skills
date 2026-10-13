#!/usr/bin/env bash
# Check that everything this skill runs is installed. Exits 1 when something required is missing.
missing=0
ok() { printf '  \342\234\223 %s\n' "$1"; }
no() { printf '  \342\234\227 %s  ->  %s\n' "$1" "$2"; missing=1; }
mac() { [ "$(uname)" = Darwin ]; }

if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then ok "ffmpeg"; else
  no "ffmpeg" "$(mac && echo 'brew install ffmpeg' || echo 'install ffmpeg with your package manager')"; fi

if command -v magick >/dev/null; then ok "ImageMagick 7 (magick)"; else
  no "ImageMagick 7 (magick)" "$(mac && echo 'brew install imagemagick' || echo 'install ImageMagick 7')"; fi

if command -v python3 >/dev/null; then
  if python3 -c 'import PIL' 2>/dev/null; then ok "Python 3 + Pillow"; else no "Pillow" "python3 -m pip install --user pillow"; fi
else no "python3" "install Python 3"; fi

if command -v node >/dev/null; then
  major="$(node -p 'process.versions.node.split(".")[0]')"
  if [ "$major" -ge 18 ]; then ok "Node $major"; else no "Node 18+ (found $major)" "upgrade Node"; fi
else no "Node 18+" "install Node (nodejs.org or nvm)"; fi

browser=""
if [ -n "${CHROME_PATH:-}" ] && [ -x "$CHROME_PATH" ]; then browser="$CHROME_PATH"; fi
for root in "$HOME/Library/Caches/ms-playwright" "$HOME/.cache/ms-playwright"; do
  [ -z "$browser" ] && [ -d "$root" ] && ls "$root" 2>/dev/null | grep -qE '^chromium(_headless_shell)?-' && browser="Playwright Chromium"
done
[ -z "$browser" ] && [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ] && browser="Google Chrome"
if [ -n "$browser" ]; then ok "Chromium for rendering ($browser)"; else
  no "Chromium for rendering" "npx playwright install chromium-headless-shell (or set CHROME_PATH)"; fi

echo "  - playwright-core is installed per project during the workflow (npm i playwright-core)"
exit $missing
