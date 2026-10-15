# Roblox Mac Linux Port

Runs the official Intel macOS Roblox client on x86_64 Linux through Darling, with Metal translated
to Vulkan. This is a continuation of spidercraft's Roblox-Mac-Linux-Port, whose repository was
deleted. It is unofficial and not affiliated with Roblox.

Compared with the last original release (2026-09-25), this version:

- Uses your desktop's own titlebar, GTK theme and cursor instead of a fixed Adwaita look.
- Survives Roblox's new titlebar experiment, which closed the original release a few seconds
  after launch or when the title bar was clicked.
- Adds a menu entry with its own icon and a Settings window.
- Asks before installing a new Roblox version.
- Shows your current game on Discord, notifies you where the game server is, runs Feral GameMode
  while you play, and tells you why Roblox closed when it crashes.
- Saves screenshots to `~/Pictures/Roblox` and recordings to `~/Videos/Roblox`.

## Requirements

- x86_64 Linux with glibc 2.43 or newer (Fedora 44 or similar) and a Wayland desktop.
- Vulkan drivers, Python 3, util-linux, curl and unzip.
- Unprivileged user namespaces.

Optional:

- PyGObject (GTK 3) for the Settings window.
- kdialog or zenity for the update prompt.
- `notify-send` for notifications.
- Feral GameMode.
- Discord, for Rich Presence.

## Install

Download `RobloxLinuxRelease.tar.gz` from the Releases page. Keep it in a short path such as
`~/RobloxLinuxRelease`; Darling can fail when socket paths get too long.

```sh
tar -xzf RobloxLinuxRelease.tar.gz -C ~
cd ~/RobloxLinuxRelease
sh update-roblox.sh   # downloads the official client and prepares shaders; takes a few minutes
sh run.sh
```

The first `run.sh` adds **Roblox (Linux)** to your application menu. Later launches can start from
there; later updates are offered automatically before launch.

## Settings

Right-click the menu entry and choose Settings, or run `sh run.sh --settings`. Settings are saved
in `DO_NOT_SHARE/config.env` and apply on the next launch:

```sh
ROBLOX_LINUX_UPDATES=ask      # ask, auto or off
ROBLOX_LINUX_DISCORD=1        # Discord Rich Presence
ROBLOX_LINUX_SERVER_NOTIFY=1  # server location, looked up with ipinfo.io
ROBLOX_LINUX_GAMEMODE=1       # Feral GameMode while Roblox runs
```

`FFlags.json` holds Roblox flag overrides and starts empty. Roblox decides which flags it accepts,
and some flags can get accounts banned, so change it only if you know what a flag does. Press F8
in a game for the runtime's Custom Settings overlay.

## Your data

`DO_NOT_SHARE/` is created on first launch. It holds your login cookies, settings, browser
storage, logs and caches. Never share it or include it in an archive. Everything else in the
folder is safe to share.

Two pieces of this release change how the Roblox client itself behaves, and you should know
about both:

- `compat/titlebar.c` adds missing macOS window functions inside the client.
- The same library keeps one client setting, `CustomTitleBarM1Enabled`, switched off in
  memory. That setting is Roblox's titlebar experiment, which draws a second title strip
  under the real titlebar.

## Troubleshooting

- `sh run.sh --diagnose` writes a system report without starting Roblox.
- Every launch logs to `DO_NOT_SHARE/diagnostics/<time>/runtime.log`. When Roblox closes
  unexpectedly, a notification gives the reason and the log's location. Review logs before sharing
  them; they can contain account details.
- A Roblox update can start calling another macOS function that Darling lacks. The crash
  notification then shows `unrecognized selector sent to instance`. Missing methods are added in
  `compat/titlebar.c`.

## How it is put together

| Path | What it does |
|---|---|
| `RobloxLinux.AppImage` | Darling, the Metal-to-Vulkan renderer and the GTK/Wayland window. Release download only. |
| `run.sh` | Launcher: desktop integration, update prompt, then the AppImage. |
| `update-roblox.sh` | Downloads the official client into `RobloxVersion/`. |
| `compat/titlebar.c` | macOS window functions Darling lacks, loaded into the client as `CoreHaptics.framework`. |
| `compat/companion.py` | Discord, server location, GameMode and crash notifications. Reads Roblox's logs. |
| `compat/settings.py` | The Settings window. |
| `compat/ui-helper-decorations.patch` | Change to the AppImage's window helper: no GTK titlebar, browser toolbar. |

## Building

`compat/build.sh` builds `compat/frameworks/CoreHaptics.framework` with clang and lld (no macOS
SDK). The release archive already contains it.

The AppImage is the 2026-09-25 original with its UI helper (`optimized/ui/libroblox-wayland.so`)
rebuilt from the source snapshot
[georgenoob1234/Roblox-Mac-Linux-Port@69908c3](https://github.com/georgenoob1234/Roblox-Mac-Linux-Port/tree/69908c3bff1176e6edcf2f869f75ebbb984cf97a/RobloxLinuxDev)
with `compat/ui-helper-decorations.patch`:

1. Apply the patch inside `RobloxLinuxDev`.
2. Fetch the pinned ImGui and Vulkan-Headers archives listed in `third_party/dependencies.json`.
3. In `runtime`, run `sh browser/build-protocols.sh` and `sh profiler/build.sh`.
4. Run the first `c++` command in `runtime/optimized/ui-build.sh`. Add
   `-ffile-prefix-map=$PWD/=` so build paths stay out of the binary. Needed packages: the
   GTK 3, WebKitGTK 4.1, json-glib, SDL3, Wayland, Xcursor and EGL/GL development packages.
5. Replace the helper with `tools/repack-appimage.sh ORIGINAL.AppImage libroblox-wayland.so OUTPUT.AppImage`.
6. Package with `tools/make-release.sh RobloxLinux.AppImage dist/`.

The helper links the C++ runtime dynamically against the AppImage's bundled libstdc++. It needs
only GLIBCXX 3.4.29, but it inherits the build machine's glibc requirement, hence glibc 2.43.

## Credits and licenses

The original project is spidercraft's. georgenoob1234 preserved the source snapshot, and this
version follows that fork's approach to window decorations.

Bundled components and their licenses are listed in [THIRD_PARTY.md](THIRD_PARTY.md) and
`licenses/`. Darling is GPL-3.0. The source for the AppImage's components is the snapshot linked
above plus this repository's patch.
