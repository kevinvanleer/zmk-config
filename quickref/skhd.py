import re
import sys

MODIFIERS = {"cmd": "⌘", "alt": "⌥", "ctrl": "⌃", "shift": "⇧"}
KEYCODES = {
    "0x33": "⌫", "0x2B": ",", "0x2F": ".", "0x21": "[", "0x1E": "]", "0x2A": "\\",
    "0x1B": "-", "0x32": "`", "0x18": "=", "0x6E": "Menu",
}
KEY_NAMES = {
    "tab": "Tab", "space": "Space", "return": "Enter", "home": "Home", "end": "End",
    "insert": "Ins", "up": "↑", "down": "↓", "left": "←", "right": "→",
}
ARROWS = {"north": "↑", "south": "↓", "west": "←", "east": "→"}
EDGES = {("top", "-"): "↑", ("top", "+"): "↓", ("bottom", "-"): "↑", ("bottom", "+"): "↓",
         ("left", "-"): "←", ("left", "+"): "→", ("right", "-"): "←", ("right", "+"): "→"}

LABELS = [
    (r"window --close", lambda m: "Close"),
    (r"space --create .*window --space", lambda m: "→Spc\nnew"),
    (r"--label ANCHOR", lambda m: "New spc\nhere"),
    (r"space --create", lambda m: "New\nspace"),
    (r"--label DESTROY", lambda m: "Kill\nspace"),
    (r"window --focus (north|south|west|east)", lambda m: f"Focus\n{ARROWS[m[1]]}"),
    (r"window --focus (prev|next)", lambda m: f"Win\n{m[1]}"),
    (r"window --swap (\w+)", lambda m: f"Swap\n{ARROWS[m[1]]}"),
    (r"space --rotate 90", lambda m: "Rotate\n↻"),
    (r"space --rotate 270", lambda m: "Rotate\n↺"),
    (r"space --mirror y-axis", lambda m: "Flip\n↔"),
    (r"space --mirror x-axis", lambda m: "Flip\n↕"),
    (r"window --resize (\w+):([-+]?\d+):([-+]?\d+)",
     lambda m: f"{m[1].title()}\n{EDGES[(m[1], '-' if '-' in m[2] + m[3] else '+')]}"),
    (r"window --display (\w+)", lambda m: f"→Disp\n{m[1]}"),
    (r"space --display (\w+)", lambda m: f"Spc→\ndisp {m[1]}"),
    (r"display --focus (\w+)", lambda m: f"Disp\n{m[1]}"),
    (r"window --space (\w+)", lambda m: f"→Spc\n{m[1].lower()}"),
    (r"space --swap (\w+)", lambda m: f"Swap\nspc {m[1].lower()}"),
    (r"space --label (\w+)", lambda m: f"Mark\n{m[1].lower()}"),
    (r"--display 2 .*\[(\d+)\]", lambda m: f"D2\nspc {int(m[1]) + 1}"),
    (r"space --focus (\w+)", lambda m: f"Space\n{m[1].lower()}"),
    (r"space --balance", lambda m: "Balance"),
    (r"--grid 1:1:0:0:1:1", lambda m: "Max"),
    (r"--grid 1:2:0:0:1:1", lambda m: "Left\nhalf"),
    (r"toggle float", lambda m: "Float"),
    (r"toggle pip", lambda m: "PiP"),
    (r"--incognito", lambda m: "Incog"),
    (r"Google Chrome", lambda m: "Chrome"),
    (r"Ghostty", lambda m: "Ghostty"),
    (r"^neovide", lambda m: "Neovide"),
    (r"Zwift", lambda m: "Zwift"),
]

BINDING = re.compile(r"^\s*(?:([a-z+ ]+?)\s*-\s*)?(0x[0-9A-Fa-f]+|\w+)\s*(?::\s*(.+)|\[)\s*$")
FALLBACK = re.compile(r'^\s*\*\s*:\s*(.+)$')


def label(command):
    for pattern, make in LABELS:
        match = re.search(pattern, command)
        if match:
            return make(match)
    print(f"skhd: no label for {command!r}", file=sys.stderr)
    return command.split()[0][:8]


def key_legend(key):
    return KEYCODES.get(key) or KEY_NAMES.get(key) or key.upper()


def logical_lines(text):
    lines = []
    for line in text.replace("\\\n", " ").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            lines.append(line)
    return lines


def parse(text):
    bindings = []
    pending = None
    for line in logical_lines(text):
        if pending:
            fallback = FALLBACK.match(line)
            if fallback:
                bindings.append((*pending, fallback[1].strip()))
            if line.strip() == "]":
                pending = None
            continue
        match = BINDING.match(line)
        if not match:
            continue
        mods = frozenset(m.strip() for m in (match[1] or "").split("+") if m.strip())
        key = key_legend(match[2])
        if match[3] is None:
            pending = (mods, key)
        else:
            bindings.append((mods, key, match[3].strip()))
    return bindings


def chord_name(mods):
    return "".join(MODIFIERS[m] for m in MODIFIERS if m in mods) or "no mod"


MIN_TAB_BINDINGS = 3


def tab_order(item):
    mods = item[0]
    return ("cmd" in mods, "alt" not in mods, len(mods), chord_name(mods))


def layers(text):
    grouped = {}
    for mods, key, command in parse(text):
        grouped.setdefault(mods, {})[key] = label(command)
    ordered = sorted(grouped.items(), key=tab_order)
    tabs = [(f"skhd {chord_name(m)}", m, keys) for m, keys in ordered if len(keys) >= MIN_TAB_BINDINGS]
    others = [
        f"{chord_name(m) if m else ''}{key}: {action}".replace("\n", " ")
        for m, keys in ordered if len(keys) < MIN_TAB_BINDINGS for key, action in keys.items()
    ]
    return tabs, others


if __name__ == "__main__":
    sample = (
        "# comment\n"
        "alt - w [\n    \"ghostty\" ~\n    *         : yabai -m window --focus north\n]\n"
        "alt + shift - 0x2B : yabai -m window --resize left:-20:0\n"
        "ctrl - 0x18 : yabai -m space --create && \\\n    yabai -m space --focus 3\n"
        "0x6E : yabai -m display --focus recent\n"
    )
    assert parse(sample) == [
        (frozenset({"alt"}), "W", "yabai -m window --focus north"),
        (frozenset({"alt", "shift"}), ",", "yabai -m window --resize left:-20:0"),
        (frozenset({"ctrl"}), "=", "yabai -m space --create &&      yabai -m space --focus 3"),
        (frozenset(), "Menu", "yabai -m display --focus recent"),
    ], parse(sample)
    assert [label(c) for _, _, c in parse(sample)] == ["Focus\n↑", "Left\n←", "New\nspace", "Disp\nrecent"]
    tabs, others = layers(sample.replace("alt + shift - 0x2B", "alt - 0x2B") + "alt - q : yabai -m window --close\n")
    assert [name for name, _, _ in tabs] == ["skhd ⌥"], tabs
    assert others == ["Menu: Disp recent", "⌃=: New space"], others
    print("ok")
