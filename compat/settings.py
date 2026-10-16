#!/usr/bin/env python3
"""Settings window for the Linux additions. Changes are written to DO_NOT_SHARE/config.env at
once and take effect on the next launch. Opened by `run.sh --settings` or the menu entry's
Settings action."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import threading

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk

# presets.py sits beside this file; python3 -I leaves the script's folder out of sys.path.
sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location('presets', Path(__file__).with_name('presets.py'))
presets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(presets)

DEFAULTS = {'ROBLOX_LINUX_UPDATES': 'ask', 'ROBLOX_LINUX_DISCORD': '1', 'ROBLOX_LINUX_SERVER_NOTIFY': '1',
            'ROBLOX_LINUX_GAMEMODE': '1', 'ROBLOX_LINUX_LINKS': '1', **presets.DEFAULTS}
UPDATE_CHOICES = [('ask', 'Ask before updating'), ('auto', 'Update automatically'), ('off', 'Never check')]
CURSOR_CHOICES = [('default', 'Default'), ('2006', 'From 2006'), ('2013', 'From 2013')]
EMOJI_CHOICES = [('default', 'Default')] + [(key, name) for key, (name, _, _) in presets.EMOJI.items()]


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


def hint_label(text=''):
    hint = Gtk.Label(label=text, xalign=0, wrap=True, max_width_chars=48)
    hint.get_style_context().add_class('dim-label')
    return hint


def row(title, hint, control):
    """A setting: its title, the dim text under it (a string or a label kept for updates), and its control."""
    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    text.pack_start(Gtk.Label(label=title, xalign=0), False, False, 0)
    if hint:
        text.pack_start(hint if isinstance(hint, Gtk.Label) else hint_label(hint), False, False, 0)
    box = Gtk.Box(spacing=24)
    box.pack_start(text, True, True, 0)
    control.set_valign(Gtk.Align.CENTER)
    box.pack_end(control, False, False, 0)
    return box


def page(notebook, title):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=20)
    notebook.append_page(box, Gtk.Label(label=title))
    return box


def choices(config, key, options):
    combo = Gtk.ComboBoxText()
    for value, label in options:
        combo.append(value, label)
    if not combo.set_active_id(config.get(key)):
        combo.set_active_id(DEFAULTS[key])
    return combo


def show_error(window, text):
    dialog = Gtk.MessageDialog(transient_for=window, modal=True, message_type=Gtk.MessageType.ERROR,
                               buttons=Gtk.ButtonsType.CLOSE, text=text)
    dialog.run()
    dialog.destroy()


def open_folder(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(['xdg-open', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build_window(release):
    config = Config(release / 'DO_NOT_SHARE/config.env')
    window = Gtk.Window(title='Roblox (Linux) settings', resizable=False)
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    notebook = Gtk.Notebook()
    outer.pack_start(notebook, False, False, 0)
    window.add(outer)

    def switch(box, key, title, subtitle, available=True):
        toggle = Gtk.Switch(active=available and config.get(key) == '1', sensitive=available)
        toggle.connect('notify::active', lambda widget, _: config.set(key, '1' if widget.get_active() else '0'))
        box.pack_start(row(title, subtitle, toggle), False, False, 0)

    content = page(notebook, 'General')
    updates = choices(config, 'ROBLOX_LINUX_UPDATES', UPDATE_CHOICES)
    updates.connect('changed', lambda combo: config.set('ROBLOX_LINUX_UPDATES', combo.get_active_id()))
    content.pack_start(section('Updates'), False, False, 0)
    content.pack_start(row('New Roblox versions', 'Checked each time Roblox starts.', updates), False, False, 0)

    content.pack_start(section('Browser'), False, False, 0)
    switch(content, 'ROBLOX_LINUX_LINKS', 'Open Roblox links here',
           'Play buttons on roblox.com start this Roblox. Turning this off gives links back to the app '
           'that had them before.')

    content.pack_start(section('While playing'), False, False, 0)
    switch(content, 'ROBLOX_LINUX_DISCORD', 'Show the game on Discord', 'Your Discord profile shows the game you are in.')
    switch(content, 'ROBLOX_LINUX_SERVER_NOTIFY', 'Show the server location',
           "A notification when you join a game, using the server's address and ipinfo.io.")
    has_gamemode = shutil.which('gamemoded') is not None
    switch(content, 'ROBLOX_LINUX_GAMEMODE', 'Use GameMode',
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

    # Bloxstrap's presets; compat/presets.py copies them into the client when Roblox starts.
    look = page(notebook, 'Appearance')
    data = release / 'DO_NOT_SHARE'
    look.pack_start(section('Look'), False, False, 0)
    cursor = choices(config, 'ROBLOX_LINUX_CURSOR', CURSOR_CHOICES)
    cursor.connect('changed', lambda combo: config.set('ROBLOX_LINUX_CURSOR', combo.get_active_id()))
    look.pack_start(row('Mouse cursor', 'The arrow Roblox shows in games.', cursor), False, False, 0)

    emoji = choices(config, 'ROBLOX_LINUX_EMOJI', EMOJI_CHOICES)
    look.pack_start(row('Emoji', 'Other emoji fonts are downloaded from Bloxstrap on GitHub when chosen.', emoji),
                    False, False, 0)
    saved_emoji = emoji.get_active_id()

    def emoji_downloaded(name, error):
        nonlocal saved_emoji
        emoji.set_sensitive(True)
        if error:
            emoji.set_active_id(saved_emoji)
            show_error(window, f'The {presets.EMOJI[name][0]} emoji could not be downloaded.\n\n{error}')
        else:
            saved_emoji = name
            config.set('ROBLOX_LINUX_EMOJI', name)

    def download_emoji(name):
        try:
            presets.fetch_emoji(data, name)
            error = None
        except (OSError, ValueError) as failure:
            error = str(failure)
        GLib.idle_add(emoji_downloaded, name, error)

    def emoji_changed(combo):
        nonlocal saved_emoji
        name = combo.get_active_id()
        if name == saved_emoji:
            return
        if name not in presets.EMOJI:
            saved_emoji = name
            config.set('ROBLOX_LINUX_EMOJI', name)
            return
        combo.set_sensitive(False)
        threading.Thread(target=download_emoji, args=(name,), daemon=True).start()

    emoji.connect('changed', emoji_changed)

    font_file = presets.custom_font(data)
    font_name_file = font_file.with_suffix('.name')
    font_button = Gtk.Button()
    font_subtitle = hint_label()
    look.pack_start(row('Font', font_subtitle, font_button), False, False, 0)

    def show_font():
        if presets.is_font(font_file):
            name = font_name_file.read_text().strip() if font_name_file.is_file() else 'A custom font'
            font_subtitle.set_text(f'{name} replaces the text font in games and menus.')
            font_button.set_label('Remove')
        else:
            font_subtitle.set_text("Roblox's own fonts.")
            font_button.set_label('Choose…')

    def font_clicked(_):
        if presets.is_font(font_file):
            font_file.unlink(missing_ok=True)
            font_name_file.unlink(missing_ok=True)
            show_font()
            return
        chooser = Gtk.FileChooserNative(title='Choose a font', transient_for=window,
                                        action=Gtk.FileChooserAction.OPEN)
        fonts = Gtk.FileFilter()
        fonts.set_name('Fonts (TTF, OTF, TTC)')
        for pattern in ('*.ttf', '*.otf', '*.ttc', '*.TTF', '*.OTF', '*.TTC'):
            fonts.add_pattern(pattern)
        chooser.add_filter(fonts)
        if chooser.run() == Gtk.ResponseType.ACCEPT:
            chosen = Path(chooser.get_filename())
            if presets.is_font(chosen):
                font_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(chosen, font_file)
                font_name_file.write_text(chosen.stem + '\n')
            else:
                show_error(window, f'{chosen.name} is not a TrueType or OpenType font.')
        chooser.destroy()
        show_font()

    font_button.connect('clicked', font_clicked)
    show_font()
    switch(look, 'ROBLOX_LINUX_OLD_AVATAR_BACKGROUND', 'Old avatar editor background',
           'The avatar editor shows the background it had in the past.')

    look.pack_start(section('Sounds'), False, False, 0)
    switch(look, 'ROBLOX_LINUX_OLD_SOUNDS', 'Old character sounds',
           'Walking, jumping and getting up sound like 2014. Falling, landing, swimming and '
           'splashing are silent.')

    note = Gtk.Label(label='Changes apply the next time Roblox starts.', xalign=0, margin=20)
    note.get_style_context().add_class('dim-label')
    note.set_margin_top(0)
    outer.pack_start(note, False, False, 0)
    window.connect('destroy', Gtk.main_quit)
    return window


if __name__ == '__main__':
    # The Wayland app ID; it matches roblox-mac.desktop, which supplies the icon.
    GLib.set_prgname('roblox-mac')
    build_window(Path(sys.argv[1])).show_all()
    Gtk.main()
