#!/bin/bash
# DocFAST installer for macOS.
#   curl -fsSL https://raw.githubusercontent.com/corefusiion/DocFAST/main/install-mac.sh | bash
# Downloads the right build for this Mac from the latest GitHub release, installs it to
# /Applications and opens it. Files fetched by curl aren't marked "downloaded from the
# internet", so macOS doesn't show the "could not verify" warning. Read it first if you like —
# it's short.
set -euo pipefail

REPO="corefusiion/DocFAST"
case "$(uname -m)" in
  arm64) ASSET="DocFAST-mac-apple-silicon.dmg" ;;
  *)     ASSET="DocFAST-mac-intel.dmg" ;;
esac
URL="https://github.com/$REPO/releases/latest/download/$ASSET"
TMP="$(mktemp -d)"
trap 'hdiutil detach "$TMP/mnt" -quiet 2>/dev/null || true; rm -rf "$TMP"' EXIT

echo "→ Downloading $ASSET"
curl -fL --progress-bar "$URL" -o "$TMP/DocFAST.dmg"

echo "→ Installing to /Applications"
hdiutil attach "$TMP/DocFAST.dmg" -mountpoint "$TMP/mnt" -nobrowse -quiet
osascript -e 'quit app "DocFAST"' 2>/dev/null || true
pkill -x DocFAST 2>/dev/null || true
DEST="/Applications/DocFAST.app"
if [ -w /Applications ]; then
  rm -rf "$DEST"; ditto "$TMP/mnt/DocFAST.app" "$DEST"
else
  sudo rm -rf "$DEST"; sudo ditto "$TMP/mnt/DocFAST.app" "$DEST"
fi
xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true

echo "→ Opening DocFAST (look for it in the menu bar)"
open "$DEST"
echo "✓ Done. Drag any file in Finder and press Shift."
