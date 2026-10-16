#!/bin/sh
# Replace the UI helper and the shader translator inside an AppImage.
#   tools/repack-appimage.sh ORIGINAL.AppImage libroblox-wayland.so metal2vulkan OUTPUT.AppImage
# Needs squashfs-tools. The original's uruntime header is reused as is.
set -eu
[ "$#" = 4 ] || { echo 'Usage: repack-appimage.sh ORIGINAL.AppImage libroblox-wayland.so metal2vulkan OUTPUT.AppImage' >&2; exit 2; }
ORIGINAL=$1 HELPER=$2 TRANSLATOR=$3 OUTPUT=$4
OFFSET=1189056  # size of the uruntime header in the 2026-09-25 release; the squashfs image follows
if [ "$(tail -c +"$((OFFSET + 1))" "$ORIGINAL" | head -c 4)" != hsqs ]; then
    echo "No squashfs image at byte $OFFSET of $ORIGINAL; this script expects the 2026-09-25 AppImage." >&2
    exit 1
fi
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
unsquashfs -q -n -no-xattrs -o "$OFFSET" -d "$work/appdir" "$ORIGINAL"
install -m 755 "$HELPER" "$work/appdir/optimized/ui/libroblox-wayland.so"
install -m 755 "$TRANSLATOR" "$work/appdir/usr/bin/metal2vulkan"
echo 'local: UI helper rebuilt from source (69908c3) with window-manager decorations, a browser toolbar and a link socket' >> "$work/appdir/BUILD-ID"
echo 'local: metal2vulkan 43c46ac rebuilt with compat/metal2vulkan.patch (float3 arrays read as float4)' >> "$work/appdir/BUILD-ID"
mksquashfs "$work/appdir" "$work/image.squashfs" -comp zstd -b 131072 -all-root -no-xattrs -noappend -quiet
head -c "$OFFSET" "$ORIGINAL" > "$work/out.AppImage"
cat "$work/image.squashfs" >> "$work/out.AppImage"
chmod 755 "$work/out.AppImage"
mv "$work/out.AppImage" "$OUTPUT"
