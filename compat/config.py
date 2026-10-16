"""DO_NOT_SHARE/config.env: KEY=value lines, read the way run.sh's setting() reads them. A line may
start with `export`, a value may be quoted, and a # comment may follow it."""
import os


def parse_line(line):
    """(key, value) for a KEY=value line, or None for comments and other lines."""
    key, equals, value = line.strip().removeprefix('export ').partition('=')
    if not equals or key.startswith('#'):
        return None
    return key.strip(), value.split('#', 1)[0].strip().strip('"\'')


def read(path, defaults):
    """The keys of `defaults` from the file; a non-empty environment variable wins, as in run.sh."""
    values = dict(defaults)
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        lines = []
    for line in lines:
        entry = parse_line(line)
        if entry and entry[0] in values:
            values[entry[0]] = entry[1]
    return {key: os.environ.get(key) or value for key, value in values.items()}
