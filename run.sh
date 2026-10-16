#!/bin/sh
# Terminal launcher with diagnostics. --diagnose checks the system without starting Roblox.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# AppImageLauncher can relocate the image or run a memfd whose parent is /.
# Keep the original image and let uruntime name its cache inside our private tmp.
umask 077
mkdir -p "$HERE/DO_NOT_SHARE/tmp"
chmod 700 "$HERE/DO_NOT_SHARE"
export APPIMAGELAUNCHER_DISABLE=1 _FORCE_HEADLESS=1
export TARGET_APPIMAGE=$HERE/RobloxLinux.AppImage
unset APPIMAGE_TARGET_DIR
export TMPDIR=$HERE/DO_NOT_SHARE/tmp TMP=$HERE/DO_NOT_SHARE/tmp TEMP=$HERE/DO_NOT_SHARE/tmp
notify() {
    command -v notify-send >/dev/null && notify-send --app-name=Roblox "--icon=$HERE/compat/roblox-linux.svg" Roblox "$1" 2>/dev/null
    echo "$1" >&2
}
# Launching needs Darling's UI socket at /Volumes/SystemRoot$HERE/DO_NOT_SHARE/launch.XXXXXX/ui.sock,
# and a Unix socket path holds at most 107 bytes; longer paths fail later with an unclear GTK error.
case "${1:-}" in --settings|--diagnose|--debug|--client-version|--download-client) ;; *)
    excess=$(( $(printf '%s' "/Volumes/SystemRoot$HERE/DO_NOT_SHARE/launch.XXXXXX/ui.sock" | wc -c) - 107 ))
    if [ "$excess" -gt 0 ]; then
        notify "This folder's path is $excess characters too long for Roblox. Move the folder somewhere shorter, such as ~/RobloxLinuxRelease."
        exit 1
    fi;;
esac
# AppKit selectors Darling lacks (see compat/titlebar.c). roblox-mac appends this guest path
# to its own DYLD_FRAMEWORK_PATH; Darling shows the host filesystem under /Volumes/SystemRoot.
if [ -f "$HERE/compat/frameworks/CoreHaptics.framework/CoreHaptics" ]; then
    export DYLD_FRAMEWORK_PATH=/Volumes/SystemRoot$HERE/compat/frameworks${DYLD_FRAMEWORK_PATH:+:$DYLD_FRAMEWORK_PATH}
fi
# update-roblox.sh calls this script with HOME and XDG_* inside DO_NOT_SHARE; desktop integration
# needs the real ones.
case "$HOME" in "$HERE/DO_NOT_SHARE"/*) desktop=;; *) desktop=1;; esac
# Window icon and menu entry: the compositor matches the helper's "roblox-mac" app ID to this desktop file.
host_data=${XDG_DATA_HOME:-$HOME/.local/share}
[ -n "$desktop" ] && case "$HERE" in *[\"\`\$\\]*) ;; *)
    icon=$host_data/icons/hicolor/scalable/apps/roblox-linux.svg
    if [ -f "$HERE/compat/roblox-linux.svg" ] && mkdir -p "$host_data/applications" "${icon%/*}"; then
        cmp -s "$HERE/compat/roblox-linux.svg" "$icon" || install -m 644 "$HERE/compat/roblox-linux.svg" "$icon"
        # A full icon path needs no icon-theme lookup or cache refresh.
        printf '%s\n' '[Desktop Entry]' 'Type=Application' 'Name=Roblox (Linux)' \
            'Comment=Roblox macOS client through Darling' "Exec=sh \"$HERE/run.sh\" %u" "Path=$HERE" \
            "Icon=$icon" 'Terminal=false' 'Categories=Game;' 'StartupWMClass=roblox-mac' \
            'MimeType=x-scheme-handler/roblox-player;x-scheme-handler/roblox;' 'Actions=settings;' '' \
            '[Desktop Action settings]' 'Name=Settings' "Exec=sh \"$HERE/run.sh\" --settings" > "$HERE/DO_NOT_SHARE/tmp/roblox-mac.desktop"
        if ! cmp -s "$HERE/DO_NOT_SHARE/tmp/roblox-mac.desktop" "$host_data/applications/roblox-mac.desktop"; then
            install -m 644 "$HERE/DO_NOT_SHARE/tmp/roblox-mac.desktop" "$host_data/applications/roblox-mac.desktop"
            command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true
        fi
        rm -f "$HERE/DO_NOT_SHARE/tmp/roblox-mac.desktop"
    fi;;
esac
# Roblox saves screenshots to ~/Pictures/Roblox and recordings to ~/Movies/Roblox in the guest.
# Darling links those guest folders to `xdg-user-dir` results for the private HOME; point them at
# the desktop's own Pictures and Videos folders.
user_dirs=
for kind in PICTURES VIDEOS; do
    dir=$(xdg-user-dir "$kind" 2>/dev/null) || dir=
    case "$dir" in *[\"\$\\\`]*) continue;; esac
    [ -d "$dir" ] && [ "$dir" != "$HOME" ] && user_dirs="${user_dirs}XDG_${kind}_DIR=\"$dir\"
"
done
if [ -n "$desktop" ] && [ -n "$user_dirs" ]; then
    mkdir -p "$HERE/DO_NOT_SHARE/config"
    printf '%s' "$user_dirs" > "$HERE/DO_NOT_SHARE/config/user-dirs.dirs"
fi
# Follow the desktop's GTK theme, titlebar buttons and cursor. The launcher gives GTK a private
# HOME and an in-memory GSettings backend, so without this the window falls back to Adwaita.
# The settings portal supplies the theme and cursor; the host's gtk-3.0 folder supplies the
# colour scheme and the titlebar button images (KDE's window-decorations module).
export GTK_USE_PORTAL=${GTK_USE_PORTAL:-1}
host_config=${XDG_CONFIG_HOME:-$HOME/.config}
if [ -n "$desktop" ] && [ -d "$host_config/gtk-3.0" ] && { [ -L "$HERE/DO_NOT_SHARE/config/gtk-3.0" ] || [ ! -e "$HERE/DO_NOT_SHARE/config/gtk-3.0" ]; }; then
    mkdir -p "$HERE/DO_NOT_SHARE/config"
    ln -sfn "$host_config/gtk-3.0" "$HERE/DO_NOT_SHARE/config/gtk-3.0"
fi
# Wayland GTK ignores gtk-modules in settings.ini; KDE's titlebar buttons come from one.
modules=$(sed -n 's/^gtk-modules *= *//p' "$host_config/gtk-3.0/settings.ini" 2>/dev/null | tail -n 1) || modules=
[ -n "$modules" ] && export GTK_MODULES=${GTK_MODULES:-$modules}
for dir in /usr/lib64/gtk-3.0 /usr/lib/x86_64-linux-gnu/gtk-3.0 /usr/lib/gtk-3.0; do
    [ -d "$dir/modules" ] && { export GTK_PATH=${GTK_PATH:-$dir}; break; }
done
# The UI helper and GTK load cursors through Xcursor, which only searches the private HOME.
icons=${XDG_DATA_HOME:-$HOME/.local/share}/icons:$HOME/.icons
old_ifs=$IFS; IFS=:
for dir in ${XDG_DATA_DIRS:-/usr/local/share:/usr/share}; do icons=$icons:$dir/icons; done
IFS=$old_ifs
export XCURSOR_PATH=${XCURSOR_PATH:-$icons:/usr/share/pixmaps}
if [ -z "${XCURSOR_THEME:-}" ] && command -v gsettings >/dev/null; then
    theme=$(gsettings get org.gnome.desktop.interface cursor-theme 2>/dev/null | tr -d "'") || theme=
    size=$(gsettings get org.gnome.desktop.interface cursor-size 2>/dev/null) || size=
    [ -n "$theme" ] && export XCURSOR_THEME=$theme
    case "$size" in ''|*[!0-9]*) ;; *) export XCURSOR_SIZE=${XCURSOR_SIZE:-$size};; esac
fi
case "${1:-}" in
    --settings) exec python3 -I "$HERE/compat/settings.py" "$HERE";;
    --diagnose|--debug|--client-version|--download-client) exec "$HERE/RobloxLinux.AppImage" "$@";;
esac
setting() {
    value=$(sed -n "s/^\\(export \\)\\{0,1\\}$1=[\"']\\{0,1\\}\\([a-z0-9]*\\).*/\\2/p" "$HERE/DO_NOT_SHARE/config.env" 2>/dev/null | tail -n 1) || value=
    eval "printf '%s' \"\${$1:-\${value:-$2}}\""
}
# Browser links (Play buttons on roblox.com). ROBLOX_LINUX_LINKS=1 makes this the desktop's handler
# for roblox: and roblox-player: links; 0 gives them back to the previous handler.
for scheme in roblox-player roblox; do
    current=$(xdg-mime query default "x-scheme-handler/$scheme" 2>/dev/null) || current=
    if [ "$(setting ROBLOX_LINUX_LINKS 1)" = 1 ]; then
        if [ "$current" != roblox-mac.desktop ]; then
            printf '%s\n' "$current" > "$HERE/DO_NOT_SHARE/previous-$scheme-handler"
            xdg-mime default roblox-mac.desktop "x-scheme-handler/$scheme" 2>/dev/null || true
        fi
    elif [ "$current" = roblox-mac.desktop ]; then
        previous=$(cat "$HERE/DO_NOT_SHARE/previous-$scheme-handler" 2>/dev/null) || previous=
        [ -n "$previous" ] && xdg-mime default "$previous" "x-scheme-handler/$scheme" 2>/dev/null || true
    fi
done
# roblox-player: links (Play buttons) carry a login ticket for the browser's account. Roblox handles
# them in a fresh process started with -protocolString, which also signs in as that account; a
# second process cannot reach the window, so the running Roblox is closed first instead.
# roblox: links go to the running client's URL handler.
link= play=
case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    roblox-player:?*) [ "$#" = 1 ] && { link=$1; play=1; shift; };;
    roblox:?*) [ "$#" = 1 ] && { link=$1; shift; };;
esac
if [ -e "$HERE/DO_NOT_SHARE/instance.lock" ] && ! flock -n "$HERE/DO_NOT_SHARE/instance.lock" true; then
    if [ -n "$play" ]; then
        if ! python3 -I "$HERE/compat/companion.py" --quit "$HERE" || ! flock -w 30 "$HERE/DO_NOT_SHARE/instance.lock" true; then
            notify 'Roblox could not be closed to open the game from your browser. Close it and try again.'
            exit 1
        fi
    elif [ -n "$link" ] && python3 -I "$HERE/compat/companion.py" --open-link "$HERE" "$link"; then
        exit 0
    else
        notify 'Roblox is already running.'
        exit 1
    fi
fi
# A new install has no client yet; download it instead of failing.
if [ ! -x "$HERE/RobloxVersion/RobloxPlayer.app/Contents/MacOS/RobloxPlayer" ]; then
    notify 'Downloading Roblox. The first download and shader preparation take a few minutes.'
    if ! sh "$HERE/update-roblox.sh"; then
        notify 'Roblox could not be downloaded. Run update-roblox.sh in a terminal for details.'
        exit 1
    fi
    flock -w 60 "$HERE/DO_NOT_SHARE/instance.lock" true || true
# The AppImage holds the shader translator; prepare shaders again after it changes.
elif [ "$(cat "$HERE/RobloxVersion/.prepared-with" 2>/dev/null || true)" != "$(stat -c '%s-%Y' "$HERE/RobloxLinux.AppImage")" ]; then
    notify "Preparing Roblox's shaders for this version of the launcher. This takes about a minute."
    sh "$HERE/update-roblox.sh" --shaders || notify 'Shader preparation failed; Roblox starts with the shaders it had.'
    flock -w 60 "$HERE/DO_NOT_SHARE/instance.lock" true || true
fi
# Roblox updates before launch. ROBLOX_LINUX_UPDATES in DO_NOT_SHARE/config.env: ask (default),
# auto or off. Offline or unanswered checks launch the installed client.
updates=$(setting ROBLOX_LINUX_UPDATES ask)
if [ "$updates" = ask ] || [ "$updates" = auto ]; then
    latest=$(timeout 15 sh "$HERE/run.sh" --client-version 2>/dev/null | sed -n '/^version-[0-9a-f][0-9a-f]*$/p') || latest=
    installed=$(cat "$HERE/RobloxVersion/.version" 2>/dev/null) || installed=
    skipped=$(cat "$HERE/DO_NOT_SHARE/skipped-version" 2>/dev/null) || skipped=
    if [ -n "$latest" ] && [ "$latest" != "$installed" ] && { [ "$updates" = auto ] || [ "$latest" != "$skipped" ]; }; then
        choice=0
        if [ "$updates" = ask ]; then
            if command -v kdialog >/dev/null; then
                timeout 60 kdialog --title 'Roblox update' --icon "$HERE/compat/roblox-linux.svg" \
                    --yes-label 'Update now' --no-label 'Not now' --cancel-label 'Skip this version' \
                    --yesnocancel 'A new version of Roblox is available. Updating takes a few minutes.' || choice=$?
            elif command -v zenity >/dev/null; then
                timeout 60 zenity --question --title='Roblox update' --ok-label='Update now' --cancel-label='Not now' \
                    --text='A new version of Roblox is available. Updating takes a few minutes.' || choice=$?
            else
                choice=1
            fi
        fi
        case $choice in
            0)
                id=$(notify-send --app-name=Roblox "--icon=$HERE/compat/roblox-linux.svg" -p Roblox 'Updating Roblox...' 2>/dev/null) || id=
                if sh "$HERE/update-roblox.sh"; then
                    notify-send --app-name=Roblox "--icon=$HERE/compat/roblox-linux.svg" ${id:+-r "$id"} Roblox 'Roblox updated.' 2>/dev/null || true
                else
                    notify-send --app-name=Roblox "--icon=$HERE/compat/roblox-linux.svg" ${id:+-r "$id"} Roblox \
                        'The update failed; launching the installed version. Run update-roblox.sh in a terminal for details.' 2>/dev/null || true
                fi
                flock -w 60 "$HERE/DO_NOT_SHARE/instance.lock" true || true;;
            2) printf '%s\n' "$latest" > "$HERE/DO_NOT_SHARE/skipped-version";;
        esac
    fi
fi
# Darling's iokitd crash-loops during a new prefix's first boot and can take Roblox down with it.
# Boot it once without Roblox; later boots are unaffected.
if [ ! -d "$HERE/DO_NOT_SHARE/prefix" ]; then
    notify 'Setting up for the first launch...'
    "$HERE/RobloxLinux.AppImage" --shell true >/dev/null 2>&1 || true
    flock -w 60 "$HERE/DO_NOT_SHARE/instance.lock" true || true
fi
if [ -n "$play" ]; then
    set -- -protocolString "$link"
    link=
fi
# Appearance options from the settings window (cursor, sounds, fonts, emoji, avatar background):
# compat/presets.py copies them into the client, or puts Roblox's own files back.
if [ -f "$HERE/compat/presets.py" ] && ! python3 -I "$HERE/compat/presets.py" apply "$HERE"; then
    notify 'Some appearance options could not be applied this time.'
fi
# Discord Rich Presence, server location, GameMode and a pending roblox: link (see
# compat/companion.py); it exits with us.
[ -f "$HERE/compat/companion.py" ] && python3 -I "$HERE/compat/companion.py" "$HERE" "$$" ${link:+"$link"} </dev/null &
exec "$HERE/RobloxLinux.AppImage" --debug "$@"
