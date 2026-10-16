#!/usr/bin/env python3
"""Appearance options taken from Bloxstrap's presets: the 2006 or 2013 mouse cursor, the old
character sounds, the old avatar editor background, a custom font and other emoji. They replace
files inside the installed client and change nothing else; no Roblox flags are involved.

  presets.py RELEASE   bring RobloxVersion in line with the settings; run.sh does this before
                       every launch

Settings (DO_NOT_SHARE/config.env, KEY=value):
  ROBLOX_LINUX_CURSOR=default        default, 2006 or 2013
  ROBLOX_LINUX_OLD_SOUNDS=0          1 = walking, jumping and getting up sound like 2014; falling,
                                     landing, swimming and splashing are silent
  ROBLOX_LINUX_OLD_AVATAR_BACKGROUND=0
  ROBLOX_LINUX_EMOJI=default         default, catmoji, windows11, windows10 or windows8
A custom font is the file DO_NOT_SHARE/presets/CustomFont.ttf; the settings window puts it there.

Every replaced file is listed in RobloxVersion/.presets.json and its original is kept in
RobloxVersion/.presets-original, so turning an option off puts Roblox's own file back. An update
replaces RobloxVersion, and the next launch applies the options to the new client.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request

# Sibling modules in compat/; python3 -I leaves the script's folder out of sys.path.
sys.path.insert(0, str(Path(__file__).parent))
sys.dont_write_bytecode = True
import config

ASSETS = Path(__file__).with_name('presets')
CLIENT = 'RobloxVersion/RobloxPlayer.app/Contents/Resources'
STATE = 'RobloxVersion/.presets.json'
ORIGINALS = 'RobloxVersion/.presets-original'
USER_AGENT = 'RobloxLinux-presets/1.0'

DEFAULTS = {'ROBLOX_LINUX_CURSOR': 'default', 'ROBLOX_LINUX_OLD_SOUNDS': '0',
            'ROBLOX_LINUX_OLD_AVATAR_BACKGROUND': '0', 'ROBLOX_LINUX_EMOJI': 'default'}

CURSORS = ('2006', '2013')
CURSOR_FILES = ('ArrowCursor.png', 'ArrowFarCursor.png')

# Bloxstrap's list; the Mac client's falling sound is Ogg Vorbis rather than MP3.
OLD_SOUNDS = {
    'content/sounds/action_footsteps_plastic.mp3': 'sounds/OldWalk.mp3',
    'content/sounds/action_jump.mp3': 'sounds/OldJump.mp3',
    'content/sounds/action_get_up.mp3': 'sounds/OldGetUp.mp3',
    'content/sounds/action_falling.ogg': 'sounds/Empty.ogg',
    'content/sounds/action_jump_land.mp3': 'sounds/Empty.mp3',
    'content/sounds/action_swim.mp3': 'sounds/Empty.mp3',
    'content/sounds/impact_water.mp3': 'sounds/Empty.mp3',
}
AVATAR_BACKGROUND = 'ExtraContent/places/Mobile.rbxl'

# Bloxstrap's emoji fonts, downloaded when chosen. The SHA-256 values are of the files whose MD5
# values Bloxstrap checks.
EMOJI_RELEASE = 'https://github.com/bloxstraplabs/rbxcustom-fontemojis/releases/download/my-phone-is-78-percent/'
EMOJI = {
    'catmoji': ('Catmoji', 'Catmoji.ttf', '58d781ff4800ab10144a6fc0bb30479881f5048ecd57196148c9ab791fdab622'),
    'windows11': ('Windows 11', 'Win1122H2SegoeUIEmoji.ttf',
                  '4e3cec7d1995b6d74102c0b4669e4507ac35cbf9a9830a93ac14c6e40dfe36a9'),
    'windows10': ('Windows 10', 'Win10April2018SegoeUIEmoji.ttf',
                  '7c0244dd8eeb7c6bdecdfc3f9e59833527fc18a66d0295ce47339069692a2b4f'),
    'windows8': ('Windows 8', 'Win8.1SegoeUIEmoji.ttf',
                 '86be288eed6561684be645f671409210c914815e3833a0fc3b587cbf64c03928'),
}
EMOJI_FONT = 'content/fonts/TwemojiMozilla.ttf'

FONT = 'content/fonts/CustomFont.ttf'
FONT_ASSET = 'rbxasset://fonts/CustomFont.ttf'
FONT_FAMILIES = 'content/fonts/families'
# TrueType, OpenType and TrueType collection signatures.
FONT_MAGIC = (b'\x00\x01\x00\x00', b'true', b'OTTO', b'ttcf')


def log(message):
    print(f'presets: {message}', file=sys.stderr, flush=True)


def custom_font(data):
    return data / 'presets/CustomFont.ttf'


def is_font(path):
    try:
        with open(path, 'rb') as file:
            return file.read(4) in FONT_MAGIC
    except OSError:
        return False


def write_atomically(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.presets-tmp')
    temporary.write_bytes(data)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def fetch_emoji(data, name):
    """Download an emoji font once and keep it in DO_NOT_SHARE/presets/emoji. Raises on failure."""
    path = data / 'presets/emoji' / EMOJI[name][1]
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == EMOJI[name][2]:
        return path
    request = urllib.request.Request(EMOJI_RELEASE + EMOJI[name][1], headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(32 << 20)
    if hashlib.sha256(body).hexdigest() != EMOJI[name][2]:
        raise ValueError(f'{EMOJI[name][1]} does not match its known checksum')
    write_atomically(path, body)
    return path


class Client:
    """The installed client's Resources folder plus the record of files replaced in it."""

    def __init__(self, release):
        self.resources = release / CLIENT
        self.state_path = release / STATE
        self.originals = release / ORIGINALS
        # A damaged record is an error, not a fresh start: starting over would back up already
        # replaced files as Roblox's originals.
        try:
            self.replaced = json.loads(self.state_path.read_text())['replaced']
        except FileNotFoundError:
            self.replaced = {}
        except (ValueError, KeyError) as error:
            raise ValueError(f'{self.state_path} is damaged ({error}). Delete the RobloxVersion folder; '
                             'the next launch downloads a clean client.') from None

    def save(self):
        write_atomically(self.state_path, json.dumps({'replaced': self.replaced}, indent=1).encode())

    def original(self, relative):
        """Roblox's own bytes for a file, or None when Roblox has no such file."""
        if relative in self.replaced:
            backup = self.originals / relative
            return backup.read_bytes() if self.replaced[relative] and backup.is_file() else None
        target = self.resources / relative
        return target.read_bytes() if target.is_file() else None

    def has(self, relative):
        return self.original(relative) is not None

    def replace(self, relative, data):
        target = self.resources / relative
        if relative not in self.replaced:
            existed = target.is_file()
            if existed:
                # The backup keeps the file's permissions, so restoring it gives back the same file.
                write_atomically(self.originals / relative, target.read_bytes(), target.stat().st_mode & 0o777)
            self.replaced[relative] = existed
            self.save()
        if not target.is_file() or target.read_bytes() != data:
            write_atomically(target, data, target.stat().st_mode & 0o777 if target.is_file() else 0o644)

    def restore(self, relative):
        target = self.resources / relative
        if self.replaced[relative]:
            backup = self.originals / relative
            if backup.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(backup, target)
            else:
                log(f'the original of {relative} is missing; the next Roblox update brings it back')
        else:
            target.unlink(missing_ok=True)
        del self.replaced[relative]
        self.save()


def wanted_files(release, client, settings):
    """Relative path in Resources -> new contents for every option that is on, and whether every
    option could be prepared."""
    data = release / 'DO_NOT_SHARE'
    wanted = {}
    complete = True
    cursor = settings['ROBLOX_LINUX_CURSOR']
    if cursor in CURSORS:
        for name in CURSOR_FILES:
            wanted[f'content/textures/Cursors/KeyboardMouse/{name}'] = (ASSETS / 'cursor' / cursor / name).read_bytes()
    if settings['ROBLOX_LINUX_OLD_SOUNDS'] == '1':
        for relative, asset in OLD_SOUNDS.items():
            if client.has(relative):
                wanted[relative] = (ASSETS / asset).read_bytes()
    if settings['ROBLOX_LINUX_OLD_AVATAR_BACKGROUND'] == '1' and client.has(AVATAR_BACKGROUND):
        wanted[AVATAR_BACKGROUND] = (ASSETS / 'OldAvatarBackground.rbxl').read_bytes()
    emoji = settings['ROBLOX_LINUX_EMOJI']
    if emoji in EMOJI:
        try:
            wanted[EMOJI_FONT] = fetch_emoji(data, emoji).read_bytes()
        except (OSError, ValueError) as error:
            log(f'the {EMOJI[emoji][0]} emoji could not be downloaded: {error}')
            complete = False
            # Keep the emoji font that is there until the download works.
            if EMOJI_FONT in client.replaced:
                wanted[EMOJI_FONT] = (client.resources / EMOJI_FONT).read_bytes()
    font = custom_font(data)
    if is_font(font):
        # Like Bloxstrap: point every face of every font family at the custom font.
        wanted[FONT] = font.read_bytes()
        families = client.resources / FONT_FAMILIES
        for path in sorted(families.glob('*.json')) if families.is_dir() else []:
            relative = f'{FONT_FAMILIES}/{path.name}'
            try:
                family = json.loads(client.original(relative))
                faces = family['faces']
            except (TypeError, ValueError, KeyError):
                continue
            for face in faces:
                face['assetId'] = FONT_ASSET
            wanted[relative] = json.dumps(family, indent='\t').encode()
    return wanted, complete


def apply(release):
    if not (release / CLIENT).is_dir():
        return True
    # Two launches at once must not both record originals; the second waits for the first.
    with open(release / 'RobloxVersion/.presets.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        client = Client(release)
        wanted, complete = wanted_files(release, client, config.read(release / 'DO_NOT_SHARE/config.env', DEFAULTS))
        for relative in list(client.replaced):
            if relative not in wanted:
                client.restore(relative)
        for relative, data in wanted.items():
            client.replace(relative, data)
    return complete


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Usage: presets.py RELEASE')
    try:
        sys.exit(0 if apply(Path(sys.argv[1])) else 1)
    except ValueError as error:
        log(str(error))
        sys.exit(1)
