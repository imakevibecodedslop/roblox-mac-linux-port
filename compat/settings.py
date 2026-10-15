#!/usr/bin/env python3
"""Settings window for the Linux additions. Changes are written to DO_NOT_SHARE/config.env at
once and take effect on the next launch. Opened by `run.sh --settings` or the menu entry's
Settings action."""
from pathlib import Path
import shutil
import subprocess
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk

DEFAULTS = {'ROBLOX_LINUX_UPDATES': 'ask', 'ROBLOX_LINUX_DISCORD': '1',
            'ROBLOX_LINUX_SERVER_NOTIFY': '1', 'ROBLOX_LINUX_GAMEMODE': '1'}
UPDATE_CHOICES = [('ask', 'Ask before updating'), ('auto', 'Update automatically'), ('off', 'Never check')]


class Config:
    """KEY=value lines in config.env; lines this window does not manage are kept as they are."""

    def __init__(self, path):
        self.path = path
        self.lines = path.read_text().splitlines() if path.exists() else []

    def get(self, key):
        for line in reversed(self.lines):
            name, _, value = line.strip().removeprefix('export ').partition('=')
            if name == key:
                return value.strip().strip('"\'')
        return DEFAULTS[key]

    def set(self, key, value):
        self.lines = [line for line in self.lines
                      if line.strip().removeprefix('export ').partition('=')[0] != key]
        self.lines.append(f'{key}={value}')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text('\n'.join(self.lines) + '\n')


def section(title):
    label = Gtk.Label(xalign=0)
    label.set_markup(f'<b>{title}</b>')
    label.set_margin_top(12)
    return label


def row(title, subtitle, control):
    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    text.pack_start(Gtk.Label(label=title, xalign=0), False, False, 0)
    if subtitle:
        hint = Gtk.Label(label=subtitle, xalign=0, wrap=True, max_width_chars=48)
        hint.get_style_context().add_class('dim-label')
        text.pack_start(hint, False, False, 0)
    box = Gtk.Box(spacing=24)
    box.pack_start(text, True, True, 0)
    control.set_valign(Gtk.Align.CENTER)
    box.pack_end(control, False, False, 0)
    return box


def open_folder(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(['xdg-open', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build_window(release):
    config = Config(release / 'DO_NOT_SHARE/config.env')
    window = Gtk.Window(title='Roblox (Linux) settings', resizable=False)
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=20)
    window.add(content)

    updates = Gtk.ComboBoxText()
    for value, label in UPDATE_CHOICES:
        updates.append(value, label)
    updates.set_active_id(config.get('ROBLOX_LINUX_UPDATES'))
    updates.connect('changed', lambda combo: config.set('ROBLOX_LINUX_UPDATES', combo.get_active_id()))
    content.pack_start(section('Updates'), False, False, 0)
    content.pack_start(row('New Roblox versions', 'Checked each time Roblox starts.', updates), False, False, 0)

    def switch(key, title, subtitle, available=True):
        toggle = Gtk.Switch(active=available and config.get(key) == '1', sensitive=available)
        toggle.connect('notify::active', lambda widget, _: config.set(key, '1' if widget.get_active() else '0'))
        content.pack_start(row(title, subtitle, toggle), False, False, 0)

    content.pack_start(section('While playing'), False, False, 0)
    switch('ROBLOX_LINUX_DISCORD', 'Show the game on Discord', 'Your Discord profile shows the game you are in.')
    switch('ROBLOX_LINUX_SERVER_NOTIFY', 'Show the server location',
           "A notification when you join a game, using the server's address and ipinfo.io.")
    has_gamemode = shutil.which('gamemoded') is not None
    switch('ROBLOX_LINUX_GAMEMODE', 'Use GameMode',
           'Feral GameMode tunes the system while Roblox runs.' if has_gamemode else 'GameMode is not installed.',
           has_gamemode)

    pictures = subprocess.run(['xdg-user-dir', 'PICTURES'], capture_output=True, text=True).stdout.strip()
    folders = Gtk.Box(spacing=8)
    for label, path in (('Screenshots', Path(pictures or Path.home() / 'Pictures') / 'Roblox'),
                        ('Logs', release / 'DO_NOT_SHARE/diagnostics')):
        button = Gtk.Button(label=label)
        button.connect('clicked', lambda _, folder=path: open_folder(folder))
        folders.pack_start(button, False, False, 0)
    content.pack_start(section('Folders'), False, False, 0)
    content.pack_start(folders, False, False, 0)

    note = Gtk.Label(label='Changes apply the next time Roblox starts.', xalign=0)
    note.get_style_context().add_class('dim-label')
    note.set_margin_top(12)
    content.pack_start(note, False, False, 0)
    window.connect('destroy', Gtk.main_quit)
    return window


if __name__ == '__main__':
    # The Wayland app ID; it matches roblox-mac.desktop, which supplies the icon.
    GLib.set_prgname('roblox-mac')
    build_window(Path(sys.argv[1])).show_all()
    Gtk.main()
