#!/bin/sh
# Replace the UI helper inside an AppImage.
#   tools/repack-appimage.sh ORIGINAL.AppImage libroblox-wayland.so OUTPUT.AppImage
# Needs squashfs-tools. The original's uruntime header is reused as is.
set -eu
[ "$#" = 3 ] || { echo 'Usage: repack-appimage.sh ORIGINAL.AppImage libroblox-wayland.so OUTPUT.AppImage' >&2; exit 2; }
ORIGINAL=$1 HELPER=$2 OUTPUT=$3
OFFSET=1189056  # size of the uruntime header in the 2026-09-25 release; the squashfs image follows
if [ "$(tail -c +"$((OFFSET + 1))" "$ORIGINAL" | head -c 4)" != hsqs ]; then
    echo "No squashfs image at byte $OFFSET of $ORIGINAL; this script expects the 2026-09-25 AppImage." >&2
    exit 1
fi
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
unsquashfs -q -n -no-xattrs -o "$OFFSET" -d "$work/appdir" "$ORIGINAL"
install -m 755 "$HELPER" "$work/appdir/optimized/ui/libroblox-wayland.so"
echo 'local: UI helper rebuilt from source (69908c3) with window-manager decorations and a browser toolbar' >> "$work/appdir/BUILD-ID"
mksquashfs "$work/appdir" "$work/image.squashfs" -comp zstd -b 131072 -all-root -no-xattrs -noappend -quiet
head -c "$OFFSET" "$ORIGINAL" > "$work/out.AppImage"
cat "$work/image.squashfs" >> "$work/out.AppImage"
chmod 755 "$work/out.AppImage"
mv "$work/out.AppImage" "$OUTPUT"
