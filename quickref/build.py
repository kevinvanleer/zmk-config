import html
import math
import os
import re
import shutil
import subprocess
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
KEYMAP_CLI = os.environ.get("KEYMAP_CLI") or shutil.which("keymap") or "keymap"

THUMBS = {
    52: "L-T1", 53: "L-T2", 54: "L-T3", 69: "L-T4", 70: "L-T5", 71: "L-T6",
    57: "R-T1", 56: "R-T2", 55: "R-T3", 74: "R-T4", 73: "R-T5", 72: "R-T6",
}


HIDDEN_LAYERS = {"Enthium", "Engrammer", "Engram", "Dvorak", "ColemakDH", "Canary"}
PINNED_LAYERS = {"QWERTY", "Cursor", "Number", "Function", "Symbol", "Magic", "CAD"}

FINGER_TAP =re.compile(r"&(?:left|right)_(?:pinky|ringy|middy|index)_tap(?= +[A-Z])")


MODIFIER_GLYPHS = {"Cmd": "⌘", "Alt": "⌥", "Ctrl": "⌃", "Shift": "⇧"}
MODIFIER_IN_CHORD = re.compile(r"([⌘⌥⌃⇧]+)(Cmd|Alt|Ctrl|Shift)$")
NAMED_CHORDS = {"⌘⌥⌃⇧": "Hyper", "⌥⌃⇧": "Meh"}


def readable(value):
    if isinstance(value, str):
        value = MODIFIER_IN_CHORD.sub(lambda m: m[1] + MODIFIER_GLYPHS[m[2]], value)
        value = NAMED_CHORDS.get(value, value)
    if not isinstance(value, str) or not value.startswith("&") or value == "&":
        return value
    words = value[1:].split()[0]
    for noise in ("emoji_", "world_", "_macro", "_status"):
        words = words.replace(noise, "")
    if words == "rgb_ug":
        return "RGB"
    return words.replace("_", " ")


HOLD_TYPES = {"Shift": "shift", "Ctrl": "ctrl", "Alt": "alt", "Cmd": "cmd"}
LOCK_LAYERS = {"Lower", "Typing"}


def key_type(key, layer_names):
    tap, hold = key.get("t"), key.get("h")
    if hold in HOLD_TYPES:
        return HOLD_TYPES[hold]
    if hold == "Magic":
        return "magic"
    if hold == "toggle" or tap in LOCK_LAYERS or hold in LOCK_LAYERS:
        return "lock"
    if hold in layer_names:
        return "layer"
    return None


def clean(key, layer_names=()):
    if key == "":
        return {"t": "", "type": "none"}
    if not isinstance(key, dict):
        key = readable(key)
        return {"t": key, "type": "lock"} if key in LOCK_LAYERS else key
    key = {k: readable(v) for k, v in key.items()}
    kind = key_type(key, layer_names)
    if "type" not in key and kind:
        key["type"] = kind
    return key


FUNCTION_LABELS = {
    "⌘⇧4": "Snip\nDesk",
    "⌘⌃⇧4": "Snip\nClip",
    "⌘Z": "Undo",
    "⌘⇧Z": "Redo",
    "⌘X": "Cut",
    "⌘C": "Copy",
    "⌘V": "Paste",
    "⌘A": "Select all",
    "⌘F": "Find",
    "⌘G": "Find next",
    "⌘⇧G": "Find prev",
    "⌘←": "Home",
    "⌘→": "End",
    "⌘H": "Hide app",
    "⌘⌃Q": "Lock screen",
    "⌃W": "VIM\nWND",
    "⌃Tab": "Next tab",
    "⌃⇧Tab": "Prev tab",
}

APP_FUNCTIONS = {
    "⌘L": ["Address bar", "Go to line"],
    "⌘K": ["Search bar", "Insert link", "Jump to", "Clear"],
}


def label_cycle(key):
    tap = str(key.get("t", "")) if isinstance(key, dict) else str(key)
    if isinstance(key, dict) and "h" in key:
        return []
    if tap in FUNCTION_LABELS:
        return [FUNCTION_LABELS[tap], tap]
    if tap in APP_FUNCTIONS:
        return [tap, *APP_FUNCTIONS[tap]]
    return []

VIM_LEADER = "["

SYMBOL_GROUPS = {
    "brackets": "()[]{}<>",
    "quotes": "'\"`",
    "operators": "=+-*/%^|&~",
    "punct": ".,;:?!",
    "other": "#$@_\\",
}


def symbolize(key, keep_shifted, variant=0):
    if not isinstance(key, dict):
        key = {"t": key}
    tap, shifted = str(key.get("t", "")), key.get("s")
    cycle = label_cycle(key)
    if cycle:
        return {"t": cycle[variant % len(cycle)], "type": "shortcut"}
    if tap.startswith("⇧") and isinstance(shifted, str) and shifted.startswith("⇧"):
        key["t"], tap = shifted[1:], shifted[1:]
        del key["s"]
    if tap == VIM_LEADER and "h" not in key:
        key.update({"type": "leader", "h": "leader"})
    if keep_shifted:
        return key
    key.pop("s", None)
    if "type" not in key and len(tap) == 1:
        for group, chars in SYMBOL_GROUPS.items():
            if tap in chars:
                key["type"] = f"sym-{group}"
    return key


KEY_CENTER = re.compile(
    r'translate\(([-\d.]+), ([-\d.]+)\)(?: rotate\(([-\d.]+)\))?" class="key[^"]*keypos-(\d+)"'
)
COLUMNS = dict(zip(range(10, 22), [6, 5, 4, 3, 2, 1, 1, 2, 3, 4, 5, 6]))
ROWS = dict(zip([0, 10, 22, 34, 46, 64], range(1, 7)))
THUMBS_LEFT = [52, 53, 54, 69, 70, 71]
THUMBS_RIGHT = [57, 56, 55, 74, 73, 72]


ROWS_BOTTOM_LEFT = 64
LEGEND = ["⌘  Cmd", "⌥  Alt", "⌃  Ctrl", "⇧  Shift", "▽  from layer below"]


def grid_labels(svg):
    matches = KEY_CENTER.findall(svg)
    centers = {int(p): (float(x), float(y)) for x, y, _, p in matches}
    angles = {int(p): math.radians(float(a or 0)) for _, _, a, p in matches}
    half = 28
    top = min(y for _, y in centers.values()) - half - 14
    right = max(x for x, _ in centers.values()) + half + 22
    labels = [(centers[p][0], top, f"C{c}") for p, c in COLUMNS.items()]
    for p, r in ROWS.items():
        y = centers[p][1] + 5
        labels += [(-22, y, f"R{r}"), (right, y, f"R{r}")]
    for cluster in (THUMBS_LEFT, THUMBS_RIGHT):
        for n, p in enumerate(cluster, 1):
            x, y = centers[p]
            a = angles[p]
            d = -42 if n <= 3 else 42
            labels.append((x - d * math.sin(a), y + d * math.cos(a) + 5, f"T{n}"))
    text = "".join(f'<text x="{x:.0f}" y="{y:.0f}" class="grid">{t}</text>' for x, y, t in labels)
    legend_top = centers[ROWS_BOTTOM_LEFT][1] + half + 30
    for n, entry in enumerate(LEGEND):
        x, y = (n % 2) * 110, legend_top + (n // 2) * 22
        text += f'<text x="{x}" y="{y:.0f}" class="legend">{html.escape(entry)}</text>'
    return f'<g transform="translate(50, 56)">{text}</g>'


SHORT_TAP = re.compile(r'(<text [^>]*class="[^"]*\btap)("[^>]*>(?:&#?\w+;|[^<&]){1,2}</text>)')


def annotate(svg):
    svg = re.sub(r'<text x="0" y="28" class="label"[^>]*>[^<]*</text>', "", svg)
    svg = SHORT_TAP.sub(r"\1 big\2", svg)
    return svg.replace("</svg>", grid_labels(svg) + "</svg>")


def keymap(*args, stdin=None):
    return subprocess.run(
        [KEYMAP_CLI, "-c", os.path.join(HERE, "config.yaml"), *args],
        input=stdin, capture_output=True, text=True, check=True,
    ).stdout


def legend(key):
    if isinstance(key, dict):
        return str(key.get("t", ""))
    return str(key)


def position_name(pos, reference_layer):
    if pos in THUMBS:
        return THUMBS[pos]
    return legend(reference_layer[pos]) or f"#{pos}"


def combo_lines(combos, layer_name, reference_layer):
    lines = []
    for combo in combos:
        if combo.get("l") and layer_name not in combo["l"]:
            continue
        keys = " + ".join(position_name(p, reference_layer) for p in combo["p"])
        key = combo["k"]
        action = legend(key)
        if isinstance(key, dict) and key.get("h") and key["h"] not in action:
            action += f" ({key['h']})"
        lines.append(f"{keys} = {action}")
    return lines


def slug(name):
    return "".join(c if c.isalnum() else "-" for c in name).lower()


def draw(parsed, layers, name):
    data = {**parsed, "layers": layers}
    svg = keymap("draw", "-", "-s", name, stdin=yaml.safe_dump(data, allow_unicode=True))
    return annotate(svg[svg.index("<svg"):])


def render(parsed, alternates, cycles):
    layers = parsed["layers"]
    combos = parsed.pop("combos", [])
    reference = next(iter(layers.values()))
    pinned, extra, sections = [], [], []
    for name in layers:
        svg = draw(parsed, layers, name)
        longest = max([1, *cycles[name].values()])
        for n, alternate in enumerate(alternates[: longest - 1], 1):
            svg += f'<div class="variant" data-n="{n}">{draw(parsed, alternate, name)}</div>'
        cycle = " ".join(f"{pos}:{m}" for pos, m in cycles[name].items())
        lines = combo_lines(combos, name, reference)
        items = "".join(f"<li>{html.escape(line)}</li>" for line in lines)
        on = ' class="on"' if not sections else ""
        tab = f'<a href="#{slug(name)}"{on}>{html.escape(name)}</a>'
        (pinned if name in PINNED_LAYERS else extra).append(tab)
        sections.append(
            f'<section id="{slug(name)}" data-combos="{len(lines)}" data-cycle="{cycle}"{on}>{svg}'
            + f'<ul class="combos">{items}</ul>'
            + "</section>"
        )
    with open(os.path.join(HERE, "page.html")) as f:
        template = f.read()
    return (
        template.replace("{{pinned}}", "".join(pinned))
        .replace("{{extra}}", "".join(extra))
        .replace("{{sections}}", "".join(sections))
    )


def main(out_path):
    with open(os.path.join(HERE, "glove80.keymap")) as f:
        source = FINGER_TAP.sub("&kp", f.read())
    parsed = yaml.safe_load(keymap("parse", "-z", "-", stdin=source))
    parsed["layout"] = {"qmk_keyboard": "glove80"}
    names = set(parsed["layers"]) - HIDDEN_LAYERS
    base = next(iter(parsed["layers"]))
    visible = {
        n: [clean(k, names) for k in keys] for n, keys in parsed["layers"].items() if n in names
    }
    cycles = {
        n: {pos: len(label_cycle(k)) for pos, k in enumerate(keys) if label_cycle(k)}
        for n, keys in visible.items()
    }
    most = max([1, *(m for c in cycles.values() for m in c.values())])
    variants = [
        {n: [symbolize(k, n == base, i) for k in keys] for n, keys in visible.items()}
        for i in range(most)
    ]
    parsed["layers"] = variants[0]
    for combo in parsed.get("combos", []):
        combo["k"] = clean(combo["k"])
    page = render(parsed, variants[1:], cycles)
    unmapped = sorted(set(re.findall(r">(&amp;[a-z][^<]*)<", page)))
    if unmapped:
        sys.exit(f"unmapped bindings: {unmapped}")
    with open(out_path, "w") as f:
        f.write(page)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "index.html"))
