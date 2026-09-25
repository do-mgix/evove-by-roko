#!/usr/bin/env bash
# Regenerates the wordmark of the APK's launch screen.
#
# The source is apps/cli/assets/media/evove-mobile-loadscreen.png, the mobile
# load screen of the visual identity: "evove / by roko" in white, sitting in the
# bottom-right corner of black. That block is 609x199 at +367+1650 of the
# 1080x1920 canvas, which — reading the canvas as xxhdpi, 360x640dp — makes it
# 203dp wide, 35dp from the right edge and 24dp from the bottom. The layer-list
# in drawable/launch_screen.xml places it at exactly those margins, so the
# proportions of the original survive on any screen instead of being stretched
# to fit one.
#
# Black is dropped to transparency: the layer underneath is already black, and
# an alpha block composites cleanly wherever else it gets reused.
#
# Needs ImageMagick. Run it from anywhere; paths are resolved from this file.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_png="$here/../../cli/assets/media/evove-mobile-loadscreen.png"
res="$here/../android/app/src/main/res"
block="$(mktemp --suffix=.png)"
trap 'rm -f "$block"' EXIT

convert "$source_png" -crop 609x199+367+1650 +repage -fuzz 5% -transparent black "$block"

# No xxxhdpi: the source is xxhdpi-sized, so that bucket would be an upscale of
# the same pixels. Android scales the xxhdpi one down and up on its own.
for entry in mdpi:203 hdpi:305 xhdpi:406 xxhdpi:609; do
  IFS=: read -r density width <<<"$entry"
  mkdir -p "$res/drawable-$density"
  convert "$block" -resize "${width}x" "$res/drawable-$density/splash_wordmark.png"
done

echo "wordmark written to $res/drawable-*/splash_wordmark.png"
