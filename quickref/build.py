import html
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


FINGER_TAP = re.compile(r"&(?:left|right)_(?:pinky|ringy|middy|index)_tap(?= +[A-Z])")


def readable(value):
    if not isinstance(value, str) or not value.startswith("&") or value == "&":
        return value
    words = value[1:].split()[0]
    for noise in ("emoji_", "world_", "_macro", "_status"):
        words = words.replace(noise, "")
    if words == "rgb_ug":
        return "RGB"
    return words.replace("_", " ")


HOLD_TYPES = {"Shift": "shift", "Ctrl": "ctrl", "Alt": "alt", "Cmd": "cmd"}


def clean(key, layer_names=()):
    if not isinstance(key, dict):
        return readable(key)
    key = {k: readable(v) for k, v in key.items()}
    hold = key.get("h")
    if "type" not in key and hold in HOLD_TYPES:
        key["type"] = HOLD_TYPES[hold]
    elif "type" not in key and hold in layer_names:
        key["type"] = "layer"
    return key


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
        if isinstance(key, dict) and key.get("h"):
            action += f" ({key['h']})"
        lines.append(f"{keys} = {action}")
    return lines


def slug(name):
    return "".join(c if c.isalnum() else "-" for c in name).lower()


def render(parsed):
    layers = parsed["layers"]
    combos = parsed.pop("combos", [])
    reference = next(iter(layers.values()))
    tabs, sections = [], []
    for name in layers:
        svg = keymap("draw", "-", "-s", name, stdin=yaml.safe_dump(parsed, allow_unicode=True))
        svg = svg[svg.index("<svg"):]
        items = "".join(f"<li>{html.escape(line)}</li>" for line in combo_lines(combos, name, reference))
        tabs.append(f'<a href="#{slug(name)}">{html.escape(name)}</a>')
        sections.append(
            f'<section id="{slug(name)}">{svg}'
            + (f'<ul class="combos">{items}</ul>' if items else "")
            + "</section>"
        )
    with open(os.path.join(HERE, "page.html")) as f:
        template = f.read()
    return template.replace("{{tabs}}", "".join(tabs)).replace("{{sections}}", "".join(sections))


def main(out_path):
    with open(os.path.join(HERE, "glove80.keymap")) as f:
        source = FINGER_TAP.sub("&kp", f.read())
    parsed = yaml.safe_load(keymap("parse", "-z", "-", stdin=source))
    parsed["layout"] = {"qmk_keyboard": "glove80"}
    names = set(parsed["layers"])
    parsed["layers"] = {n: [clean(k, names) for k in keys] for n, keys in parsed["layers"].items()}
    for combo in parsed.get("combos", []):
        combo["k"] = clean(combo["k"])
    page = render(parsed)
    unmapped = sorted(set(re.findall(r">(&amp;[a-z][^<]*)<", page)))
    if unmapped:
        sys.exit(f"unmapped bindings: {unmapped}")
    with open(out_path, "w") as f:
        f.write(page)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "index.html"))
