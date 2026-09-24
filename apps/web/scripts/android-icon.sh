#!/usr/bin/env bash
# Regenerates the launcher icons of the APK from the evove wordmark.
#
# The mark is the first "e" of apps/cli/assets/media/evovepng.png — the wordmark
# itself is illegible at 48dp, so the icon is that single letter, white on the
# app's black. The crop below is the letter's bounding box inside the 1080x1080
# source: the wordmark occupies 596x95 at +242+478, and its letters are split by
# four columns of pure black, the first at x=113.
#
# Needs ImageMagick. Run it from anywhere; paths are resolved from this file.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_png="$here/../../cli/assets/media/evovepng.png"
res="$here/../android/app/src/main/res"
glyph="$(mktemp --suffix=.png)"
trap 'rm -f "$glyph"' EXIT

convert "$source_png" -crop 113x95+242+478 +repage "$glyph"

# density:legacy size:adaptive foreground size
for entry in mdpi:48:108 hdpi:72:162 xhdpi:96:216 xxhdpi:144:324 xxxhdpi:192:432; do
  IFS=: read -r density legacy adaptive <<<"$entry"
  dir="$res/mipmap-$density"

  # Adaptive foreground: the launcher masks everything outside the inner 72dp of
  # 108dp and may animate within it, so the glyph stays inside the 66dp safe
  # zone — 55% of the canvas here.
  convert -size "${adaptive}x${adaptive}" xc:none \
    \( "$glyph" -resize "$((adaptive * 55 / 100))x" \) \
    -gravity center -composite "$dir/ic_launcher_foreground.png"

  # Legacy icons, for launchers that predate adaptive icons: the same letter,
  # composited on black, square and round.
  convert -size "${legacy}x${legacy}" xc:black \
    \( "$glyph" -resize "$((legacy * 60 / 100))x" \) \
    -gravity center -composite "$dir/ic_launcher.png"

  convert -size "${legacy}x${legacy}" xc:none \
    -fill black -draw "ellipse $((legacy / 2)),$((legacy / 2)) $((legacy / 2)),$((legacy / 2)) 0,360" \
    \( "$glyph" -resize "$((legacy * 55 / 100))x" \) \
    -gravity center -composite "$dir/ic_launcher_round.png"
done

echo "icons written to $res/mipmap-*"
