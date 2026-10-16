> **AI SLOP DISCLAIMER/TRANSPARENCY:** this port was written entirely by claude code, play tested by me. this disclaimer is the only text that hasnt been generated with ai, rest of this project is considered **ai slop.** use this at your own risk and please report issues if there are any. 

![Roblox Mac Linux Port](docs/banner.png)

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
- Opens Play buttons and other Roblox links from your browser, including while Roblox is running.
  A Play button signs Roblox in as the account your browser is using, so it switches accounts.
- Fixes two crashes in Darling: one during the very first launch, and one in its audio code
  that closed Roblox mid-game.
- Translates all of Roblox's shaders to Vulkan. The original translator rejected 12 lighting
  shaders, which could leave parts of some games drawn wrong.

## Requirements

- x86_64 Linux with glibc 2.39 or newer (Ubuntu 24.04, Fedora 40 or newer) and a Wayland desktop.
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
sh ~/RobloxLinuxRelease/run.sh
```

The first launch downloads the official client and prepares its shaders, which takes a few
minutes, then boots Darling once on its own before starting Roblox. It also adds
**Roblox (Linux)** to your application menu and makes it the handler for Roblox links in your
browser. Later launches can start from the menu, and new Roblox versions are offered before
launch. `sh update-roblox.sh` updates by hand, and `sh update-roblox.sh --shaders` prepares the
installed client's shaders again. That also happens by itself the first time a new AppImage starts,
because the shader translator lives in the AppImage.

## Settings

Right-click the menu entry and choose Settings, or run `sh run.sh --settings`. Settings are saved
in `DO_NOT_SHARE/config.env` and apply on the next launch:

```sh
ROBLOX_LINUX_UPDATES=ask      # ask, auto or off
ROBLOX_LINUX_DISCORD=1        # Discord Rich Presence
ROBLOX_LINUX_SERVER_NOTIFY=1  # server location, looked up with ipinfo.io
ROBLOX_LINUX_GAMEMODE=1       # Feral GameMode while Roblox runs
ROBLOX_LINUX_LINKS=1          # open roblox: and roblox-player: links here; 0 hands them back
```

A Play button (`roblox-player:` link) restarts Roblox if it is already open: the Mac client handles
these links in a new process, and that process signs in with the ticket in the link. `roblox:`
links go to the running client without a restart.

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

`compat/audio.c` changes Darling's AudioToolbox, not Roblox: stopping an audio unit that is already
closed returns an error, as on macOS, instead of crashing.

## Troubleshooting

- `sh run.sh --diagnose` writes a system report without starting Roblox.
- Every launch logs to `DO_NOT_SHARE/diagnostics/<time>/runtime.log`. When Roblox closes
  unexpectedly, a notification gives the reason and the log's location. Review logs before sharing
  them; they can contain account details.
- A Roblox update can start calling another macOS function that Darling lacks. The crash
  notification then shows `unrecognized selector sent to instance`. Missing methods are added in
  `compat/titlebar.c`.
- Crashes inside Darling leave a register dump in `DO_NOT_SHARE/crashes/fatal.log`; the crash
  notification points there when that happens.

## How it is put together

| Path | What it does |
|---|---|
| `RobloxLinux.AppImage` | Darling, the Metal-to-Vulkan renderer and the GTK/Wayland window. Release download only. |
| `run.sh` | Launcher: desktop integration, update prompt, then the AppImage. |
| `update-roblox.sh` | Downloads the official client into `RobloxVersion/`. |
| `compat/titlebar.c` | macOS window functions Darling lacks, loaded into the client as `CoreHaptics.framework`. |
| `compat/audio.c` | Guard against Darling's AudioToolbox crash on closed audio units; same framework. |
| `compat/companion.py` | Discord, server location, GameMode, crash notifications and pending browser links. Reads Roblox's logs. |
| `compat/settings.py` | The Settings window. |
| `compat/metal2vulkan.patch` | Fix to the shader translator: reads of a `float3` array as `float4`, which Metal allows. |
| `compat/ui-helper.patch` | Change to the AppImage's window helper: no GTK titlebar, browser toolbar, and a socket that passes browser links to a running Roblox. |

## Building

`compat/build.sh` builds `compat/frameworks/CoreHaptics.framework` with clang and lld (no macOS
SDK). The release archive already contains it.

The AppImage is the 2026-09-25 original with its UI helper (`optimized/ui/libroblox-wayland.so`)
rebuilt from the source snapshot
[georgenoob1234/Roblox-Mac-Linux-Port@69908c3](https://github.com/georgenoob1234/Roblox-Mac-Linux-Port/tree/69908c3bff1176e6edcf2f869f75ebbb984cf97a/RobloxLinuxDev)
with `compat/ui-helper.patch`:

1. Apply the patch inside `RobloxLinuxDev`.
2. Fetch the pinned ImGui and Vulkan-Headers archives listed in `third_party/dependencies.json`.
3. In `runtime`, run `sh browser/build-protocols.sh` and `sh profiler/build.sh`.
4. Run the first `c++` command in `runtime/optimized/ui-build.sh`. For step 3 and this one, add
   `-include tools/glibc-baseline.h` and `-ffile-prefix-map=$PWD/=` to every compile (a `c++`
   wrapper script first in `PATH` does it), so the helper runs on glibc 2.39 and build paths stay
   out of the binary. Needed packages: the GTK 3, WebKitGTK 4.1, json-glib, SDL3, Wayland, Xcursor
   and EGL/GL development packages.
5. Build the shader translator: check out
   [steelbrain/metal2vulkan](https://github.com/steelbrain/metal2vulkan) at the commit pinned in
   `third_party/dependencies.json`, apply `third_party/patches/metal2vulkan.patch` and then
   `compat/metal2vulkan.patch`, copy `third_party/metal2vulkan-Cargo.lock` to `Cargo.lock`, and run
   `cargo build --release --locked --features serde --bin metal2vulkan`. Pass
   `--remap-path-prefix` in `RUSTFLAGS` to keep build paths out of the binary.
6. Replace both with `tools/repack-appimage.sh ORIGINAL.AppImage libroblox-wayland.so metal2vulkan OUTPUT.AppImage`.
7. Package with `tools/make-release.sh RobloxLinux.AppImage dist/`.

The helper links the C++ runtime dynamically against the AppImage's bundled libstdc++ and needs at
most GLIBCXX 3.4.29 and GLIBC 2.38, the same as the original helper.

## Credits and licenses

The original project is spidercraft's. georgenoob1234 preserved the source snapshot, and this
version follows that fork's approach to window decorations.

Bundled components and their licenses are listed in [THIRD_PARTY.md](THIRD_PARTY.md) and
`licenses/`. Darling is GPL-3.0. The source for the AppImage's components is the snapshot linked
above plus this repository's patch.
