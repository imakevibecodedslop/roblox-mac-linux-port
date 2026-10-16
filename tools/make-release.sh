#!/bin/sh
# Build RobloxLinuxRelease.tar.gz from this repository and a finished AppImage.
#   tools/make-release.sh RobloxLinux.AppImage OUTPUT_DIR
# The archive holds no Roblox client and no DO_NOT_SHARE data; users run update-roblox.sh.
set -eu
[ "$#" = 2 ] || { echo 'Usage: make-release.sh RobloxLinux.AppImage OUTPUT_DIR' >&2; exit 2; }
REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
APPIMAGE=$1 OUT=$2
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
STAGE=$work/RobloxLinuxRelease
mkdir -p "$STAGE/compat" "$OUT"
cp "$REPO/run.sh" "$REPO/update-roblox.sh" "$REPO/FFlags.json" "$REPO/README.md" "$REPO/THIRD_PARTY.md" \
    "$REPO/LICENSE" "$REPO/.gitignore" "$STAGE/"
cp -r "$REPO/licenses" "$REPO/docs" "$STAGE/"
for file in titlebar.c audio.c macho.h build.sh companion.py settings.py presets.py config.py roblox-linux.svg \
    ui-helper.patch metal2vulkan.patch; do
    cp "$REPO/compat/$file" "$STAGE/compat/"
done
cp -r "$REPO/compat/presets" "$STAGE/compat/"
sh "$STAGE/compat/build.sh" >/dev/null
install -m 755 "$APPIMAGE" "$STAGE/RobloxLinux.AppImage"
tar --owner=0 --group=0 --numeric-owner -czf "$OUT/RobloxLinuxRelease.tar.gz" -C "$work" RobloxLinuxRelease
(cd "$OUT" && sha256sum RobloxLinuxRelease.tar.gz > RobloxLinuxRelease.tar.gz.sha256)
echo "Built $OUT/RobloxLinuxRelease.tar.gz"
