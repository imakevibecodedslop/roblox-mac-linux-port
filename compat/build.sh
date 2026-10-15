#!/bin/sh
# Build compat/frameworks/CoreHaptics.framework from titlebar.c with clang and lld (ld64.lld).
# Text stubs stand in for the macOS SDK; Darling supplies the real libobjc and AppKit at runtime.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUT=$HERE/frameworks/CoreHaptics.framework
work=$(mktemp -d)
trap 'command rm -rf -- "$work"' EXIT
cat > "$work/libobjc.tbd" <<'EOF'
--- !tapi-tbd
tbd-version: 4
targets: [ x86_64-macos ]
install-name: '/usr/lib/libobjc.A.dylib'
exports:
  - targets: [ x86_64-macos ]
    symbols: [ _objc_getClass, _sel_registerName, _class_getInstanceMethod, _class_addMethod, _objc_msgSend_stret ]
...
EOF
cat > "$work/libSystem.tbd" <<'EOF'
--- !tapi-tbd
tbd-version: 4
targets: [ x86_64-macos ]
install-name: '/usr/lib/libSystem.B.dylib'
exports:
  - targets: [ x86_64-macos ]
    symbols: [ dyld_stub_binder, _write, __dyld_get_image_header, __dyld_get_image_vmaddr_slide,
               _pthread_create, _usleep ]
...
EOF
# Depending on AppKit makes dyld initialize it, and register NSWindow, before our constructor.
cat > "$work/AppKit.tbd" <<'EOF'
--- !tapi-tbd
tbd-version: 4
targets: [ x86_64-macos ]
install-name: '/System/Library/Frameworks/AppKit.framework/Versions/C/AppKit'
...
EOF
clang -target x86_64-apple-macos10.15 -O2 -fno-stack-protector -c "$HERE/titlebar.c" -o "$work/titlebar.o"
mkdir -p "$OUT/Versions/A"
ld64.lld -dylib -arch x86_64 -platform_version macos 10.15 10.15 \
    -install_name /System/Library/Frameworks/CoreHaptics.framework/Versions/A/CoreHaptics \
    -o "$OUT/Versions/A/CoreHaptics" "$work/titlebar.o" "$work/libobjc.tbd" "$work/libSystem.tbd" -needed_library "$work/AppKit.tbd"
ln -sfn A "$OUT/Versions/Current"
ln -sfn Versions/Current/CoreHaptics "$OUT/CoreHaptics"
echo "Built $OUT"
