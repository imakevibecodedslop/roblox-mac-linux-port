#!/usr/bin/env python3
"""Desktop integration that runs beside Roblox: Discord Rich Presence, a server-location
notification when joining a game, Feral GameMode, a notification when Roblox crashes, and
delivery of a browser link once Roblox is ready. It reads Roblox's own logs and never touches
the client. Started by run.sh; exits when the launcher process it watches exits.

Settings (DO_NOT_SHARE/config.env, KEY=value, 1 = on, 0 = off):
  ROBLOX_LINUX_DISCORD=1         show the current game on your Discord profile
  ROBLOX_LINUX_SERVER_NOTIFY=1   notify where the game server is (looks up the server's IP
                                 address with ipinfo.io)
  ROBLOX_LINUX_GAMEMODE=1        request Feral GameMode while Roblox runs, if installed
"""
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.request
import uuid

# Bloxstrap's public Discord application, named "Roblox"; Discord shows its name and fallback art.
DISCORD_CLIENT_ID = '1005469189907173486'
USER_AGENT = 'RobloxLinux-companion/1.0'
ICON = Path(__file__).with_name('roblox-linux.svg')

JOIN = re.compile(r"! Joining game '[0-9a-f-]+' place (\d+)")
UDMUX = re.compile(r'UDMUX Address = ([0-9.]+)')
LEAVE = re.compile(r'leaveUGCGameInternal|Time to disconnect replication data')
RPC = re.compile(r'\[BloxstrapRPC\] (\{.*\})')
RESULT = re.compile(r'^Runtime result: (exit (\d+)|signal (\d+) \((\w+)\))')
CRASH = re.compile(r'RBXCRASH: (?:UnhandledException \()?(.*?)\)?$')
# Darling reports its own failures between asterisks, e.g. "*** dserver_rpc_interrupt_enter failed ***".
DARLING_ERROR = re.compile(r'^\*\*\* (.+) \*\*\*$')
READY = re.compile(r'setStage: \(stage:LuaApp\)')
LINK_TIMEOUT = 60
# Stopping Roblox from its terminal or the session ending is not a crash, and exit 73 means
# another Roblox already held the instance lock.
QUIET_SIGNALS = {'SIGINT', 'SIGTERM', 'SIGHUP'}
QUIET_EXITS = {'0', '73'}


def log(message):
    print(f'companion: {message}', file=sys.stderr, flush=True)


def read_settings(data):
    values = {'ROBLOX_LINUX_DISCORD': '1', 'ROBLOX_LINUX_SERVER_NOTIFY': '1', 'ROBLOX_LINUX_GAMEMODE': '1'}
    try:
        lines = (data / 'config.env').read_text().splitlines()
    except FileNotFoundError:
        lines = []
    for line in lines:
        key, _, value = line.strip().removeprefix('export ').partition('=')
        if key in values:
            values[key] = value.strip().strip('"\'')
    return {key: os.environ.get(key, value) == '1' for key, value in values.items()}


def notify(title, body):
    if shutil.which('notify-send'):
        subprocess.Popen(['notify-send', '--app-name=Roblox', f'--icon={ICON}', title, body],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def get_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


class Discord:
    """Discord IPC: a handshake, then SET_ACTIVITY frames. Safe to call from several threads."""

    def __init__(self):
        self.sock = None
        self.lock = threading.Lock()

    @staticmethod
    def socket_paths():
        base = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
        for folder in (base, base / 'app/com.discordapp.Discord', base / 'app/dev.vencord.Vesktop', base / 'snap.discord'):
            for i in range(10):
                yield folder / f'discord-ipc-{i}'

    def send(self, op, payload):
        body = json.dumps(payload).encode()
        self.sock.sendall(struct.pack('<II', op, len(body)) + body)
        header = self.sock.recv(8)
        if len(header) < 8:
            raise ConnectionError('Discord closed the connection')
        _, length = struct.unpack('<II', header)
        while length:
            chunk = self.sock.recv(min(length, 65536))
            if not chunk:
                raise ConnectionError('Discord closed the connection')
            length -= len(chunk)

    def connect(self):
        for path in self.socket_paths():
            if not path.exists():
                continue
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            try:
                self.sock.connect(str(path))
                self.send(0, {'v': 1, 'client_id': DISCORD_CLIENT_ID})
                return True
            except OSError:
                self.close()
        return False

    def set_activity(self, activity):
        payload = {'cmd': 'SET_ACTIVITY', 'args': {'pid': os.getpid(), 'activity': activity}, 'nonce': str(uuid.uuid4())}
        with self.lock:
            # A second attempt reconnects after Discord restarts; if it is not running, skip quietly.
            for _ in range(2):
                try:
                    if self.sock or self.connect():
                        self.send(1, payload)
                    return
                except OSError:
                    self.close()

    def close(self):
        if self.sock:
            self.sock.close()
        self.sock = None


class Game:
    def __init__(self, place):
        self.place, self.start = place, int(time.time())
        self.name = self.creator = self.icon = None
        self.custom = {}

    def activity(self):
        details = self.custom.get('details') or self.name or 'In a game'
        state = self.custom.get('state') or (f'by {self.creator}' if self.creator else None)
        activity = {'details': details[:128],
                    'timestamps': {'start': self.custom.get('timeStart') or self.start},
                    'assets': {'large_image': self.icon or 'roblox', 'large_text': (self.name or 'Roblox')[:128],
                               'small_image': 'roblox', 'small_text': 'Roblox'},
                    'buttons': [{'label': 'See game page', 'url': f'https://www.roblox.com/games/{self.place}'}]}
        if state:
            activity['state'] = state[:128]
        if self.custom.get('timeEnd'):
            activity['timestamps']['end'] = self.custom['timeEnd']
        return activity


def send_to_client(release, message):
    """Send a roblox: link, or "quit", to the running client through the UI helper's link socket."""
    for path in (release / 'DO_NOT_SHARE').glob('launch.*/links.sock'):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(5)
            try:
                connection.connect(str(path))
                connection.sendall(message.encode() + b'\n')
                return True
            except OSError:
                continue  # a leftover socket from an earlier session
    return False


class Companion:
    def __init__(self, release, launcher_pid, link=None):
        self.data = release / 'DO_NOT_SHARE'
        self.launcher_pid = launcher_pid
        self.link = link
        self.settings = read_settings(self.data)
        self.discord = Discord() if self.settings['ROBLOX_LINUX_DISCORD'] else None
        self.game = None
        self.started = time.time()
        self.client_started = None

    def update_presence(self):
        if not self.discord:
            return
        game = self.game
        if game:
            self.discord.set_activity(game.activity())
        elif self.client_started:
            # "roblox" is an image in the Discord application's own assets.
            self.discord.set_activity({'details': 'In the menus', 'timestamps': {'start': self.client_started},
                                       'assets': {'large_image': 'roblox', 'large_text': 'Roblox'}})

    def look_up_game(self, game):
        try:
            universe = get_json(f'https://apis.roblox.com/universes/v1/places/{game.place}/universe')['universeId']
            if not universe:
                raise ValueError('the place is private or unavailable')
            info = get_json(f'https://games.roblox.com/v1/games?universeIds={universe}')['data'][0]
            icons = get_json('https://thumbnails.roblox.com/v1/games/icons?universeIds='
                             f'{universe}&returnPolicy=PlaceHolder&size=512x512&format=Png&isCircular=false')
            game.name, game.creator = info.get('name'), info.get('creator', {}).get('name')
            game.icon = icons['data'][0].get('imageUrl')
        except (OSError, ValueError, KeyError, IndexError) as error:
            log(f'could not look up place {game.place}: {error}')
            return
        if self.game is game:
            self.update_presence()

    def notify_server_location(self, game, address):
        try:
            info = get_json(f'https://ipinfo.io/{address}/json')
        except (OSError, ValueError) as error:
            log(f'could not locate server {address}: {error}')
            return
        location = ', '.join(part for part in (info.get('city'), info.get('region'), info.get('country')) if part)
        if self.game is game and location:
            notify('Connected to a Roblox server', f'Located in {location}')

    def handle_line(self, line):
        if match := JOIN.search(line):
            self.game = Game(int(match[1]))
            self.update_presence()
            threading.Thread(target=self.look_up_game, args=(self.game,), daemon=True).start()
        elif (match := UDMUX.search(line)) and self.game and self.settings['ROBLOX_LINUX_SERVER_NOTIFY']:
            threading.Thread(target=self.notify_server_location, args=(self.game, match[1]), daemon=True).start()
        elif LEAVE.search(line) and self.game:
            self.game = None
            self.update_presence()
        elif (match := RPC.search(line)) and self.game:
            self.apply_game_status(match[1])
        elif self.link and READY.search(line):
            self.deliver_link()

    def deliver_link(self):
        if not send_to_client(self.data.parent, self.link):
            log('could not hand the link to Roblox')
        self.link = None

    def apply_game_status(self, text):
        # Games can set their own status with BloxstrapRPC; text and times only.
        try:
            message = json.loads(text)
        except ValueError:
            return
        if not isinstance(message, dict) or message.get('command') != 'SetRichPresence':
            return
        data = message.get('data')
        if not isinstance(data, dict):
            return
        for key, kind in (('details', str), ('state', str), ('timeStart', int), ('timeEnd', int)):
            if isinstance(data.get(key), kind):
                self.game.custom[key] = data[key] or None
        self.update_presence()

    def newest_log(self):
        newest, newest_time = None, self.started - 5
        for path in (self.data / 'prefix/Users/root/Library/Logs/Roblox').glob('*_Player_*_last.log'):
            try:
                modified = path.stat().st_mtime
            except FileNotFoundError:
                continue
            if 'CrashHandler' not in path.name and modified >= newest_time:
                newest, newest_time = path, modified
        return newest

    def launcher_alive(self):
        try:
            stat = Path(f'/proc/{self.launcher_pid}/stat').read_text()
        except FileNotFoundError:
            return False
        return stat.rpartition(')')[2].split()[0] not in ('Z', 'X')

    @staticmethod
    def client_pid():
        # The client itself, not the guest shell whose command line also names it.
        pids = subprocess.run(['pgrep', '-f', '^/Volumes/SystemRoot/.*/RobloxPlayer.app/Contents/MacOS/RobloxPlayer '],
                              capture_output=True, text=True).stdout.split()
        return pids[-1] if pids else None

    @staticmethod
    def gamemode(method, pid):
        subprocess.run(['gdbus', 'call', '--session', '--timeout', '5', '--dest', 'com.feralinteractive.GameMode',
                        '--object-path', '/com/feralinteractive/GameMode',
                        '--method', f'com.feralinteractive.GameMode.{method}', str(os.getpid()), pid],
                       capture_output=True, check=False)

    def run(self):
        use_gamemode = self.settings['ROBLOX_LINUX_GAMEMODE'] and shutil.which('gdbus') and shutil.which('gamemoded')
        path, log_file, partial, client = None, None, '', None
        while self.launcher_alive():
            if use_gamemode and not client and (client := self.client_pid()):
                self.gamemode('RegisterGameByPID', client)
            newest = self.newest_log()
            if newest and newest != path:
                if log_file:
                    log_file.close()
                path, log_file, partial = newest, open(newest, errors='replace'), ''
                if not self.client_started:
                    self.client_started = int(time.time())
                    self.update_presence()
            if self.link and time.time() - self.started > LINK_TIMEOUT:
                self.deliver_link()
            chunk = log_file.read() if log_file else ''
            if not chunk:
                time.sleep(0.5)
                continue
            *lines, partial = (partial + chunk).split('\n')
            for line in lines:
                self.handle_line(line)
        if client:
            self.gamemode('UnregisterGameByPID', client)
        if self.discord:
            self.discord.close()
        self.report_crash()

    def report_crash(self):
        # The launcher writes this run's log under DO_NOT_SHARE/diagnostics, ending with its exit status.
        runs = [run for run in (self.data / 'diagnostics').glob('*/runtime.log') if run.stat().st_mtime >= self.started]
        if not runs:
            return
        run_log = max(runs, key=lambda run: run.stat().st_mtime)
        reason, status = None, None
        for line in run_log.read_text(errors='replace').splitlines():
            if match := CRASH.search(line) or DARLING_ERROR.match(line):
                reason = match[1]
            elif match := RESULT.match(line):
                status = match
        if not status or status[2] in QUIET_EXITS or status[4] in QUIET_SIGNALS:
            return
        log_path = run_log.relative_to(self.data.parent)
        # Native crashes in the client leave a register dump in crashes/fatal.log instead.
        fatal = self.data / 'crashes/fatal.log'
        # The runtime creates it empty at launch and appends a report for each fault.
        if not reason and fatal.exists() and fatal.stat().st_size and fatal.stat().st_mtime >= self.started:
            reason = 'The client crashed inside the compatibility layer'
            log_path = fatal.relative_to(self.data.parent)
        notify('Roblox closed unexpectedly', f'{reason or status[1]}\nLog: {log_path}')


if __name__ == '__main__':
    if sys.argv[1] == '--open-link':
        sys.exit(0 if send_to_client(Path(sys.argv[2]), sys.argv[3]) else 1)
    if sys.argv[1] == '--quit':
        sys.exit(0 if send_to_client(Path(sys.argv[2]), 'quit') else 1)
    try:
        Companion(Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None).run()
    except KeyboardInterrupt:
        pass  # Ctrl+C in the launching terminal reaches this process too; exit without a traceback.
