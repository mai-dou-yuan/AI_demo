#!/usr/bin/env bash
# Capture the real login screen in a fresh browser profile, without private session data.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
SCREENSHOT_ROOT="$PWD"
SCREENSHOT_BROWSER=""
for candidate in google-chrome chromium chromium-browser; do
  if command -v "$candidate" >/dev/null 2>&1; then SCREENSHOT_BROWSER="$(command -v "$candidate")"; break; fi
done
[[ -n "$SCREENSHOT_BROWSER" ]] || { echo '需要本机已有的 Chrome/Chromium；也可按 docs/screenshots/README.md 手动截图。' >&2; exit 1; }
curl --noproxy '*' -fsS --connect-timeout 3 --max-time 10 -o /dev/null http://127.0.0.1:3000/ || { echo '请先运行 bash scripts/dev.sh 或 bash scripts/dev.sh lan。' >&2; exit 1; }
mkdir -p docs/screenshots
SCREENSHOT_PROFILE="$(mktemp -d)"
trap 'rm -rf -- "$SCREENSHOT_PROFILE"' EXIT
"$SCREENSHOT_BROWSER" --headless --disable-gpu --disable-dev-shm-usage --no-first-run \
  --hide-scrollbars --force-device-scale-factor=1 --window-size=1440,1000 \
  --virtual-time-budget=8000 --user-data-dir="$SCREENSHOT_PROFILE" \
  --screenshot="$SCREENSHOT_ROOT/docs/screenshots/login.png" http://127.0.0.1:3000/
"$SCREENSHOT_ROOT/.conda/ai-brain/bin/python" scripts/update_readme_screenshots.py
echo '已生成登录页截图并更新 README 图片引用。发布前请打开图片确认截取正确。'
