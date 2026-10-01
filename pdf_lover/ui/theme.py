"""Hallmark · Catalogue home / Workbench tool · Cobalt · native Windows adaptation.

Pre-emit critique: Philosophy 4 / Hierarchy 5 / Execution 4 /
Specificity 5 / Restraint 5 / Variety 4.
OKLCH is the source of truth; Tk receives converted sRGB tokens.
"""

import math

PALETTE = {
    "paper": (0.978, 0.005, 250),
    "surface": (0.996, 0.002, 250),
    "soft": (0.948, 0.009, 250),
    "ink": (0.245, 0.024, 258),
    "muted": (0.485, 0.025, 258),
    "rule": (0.885, 0.014, 250),
    "accent": (0.525, 0.205, 260),
    "accent-hover": (0.465, 0.19, 260),
    "accent-pressed": (0.405, 0.16, 260),
    "accent-ink": (0.996, 0.002, 250),
    "tint": (0.95, 0.023, 260),
    "focus": (0.175, 0.018, 258),
    "success": (0.425, 0.10, 155),
    "error": (0.485, 0.17, 26),
    "graphite": (0.245, 0.024, 258),
    "graphite-muted": (0.79, 0.018, 250),
}
FONTS = {"display": "Segoe UI", "body": "Leelawadee UI", "mono": "Cascadia Code"}
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 40}
RADIUS = {"control": 8, "panel": 16}


def srgb(lightness, chroma, hue):
    angle = math.radians(hue)
    a, b = chroma * math.cos(angle), chroma * math.sin(angle)
    l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    channels = (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )
    def encode(value):
        value = max(0, min(1, value))
        return round(255 * (12.92 * value if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055))
    return "#" + "".join(f"{encode(channel):02x}" for channel in channels)


COLORS = {name: srgb(*value) for name, value in PALETTE.items()}


def export_css():
    lines = ["/* Hallmark · macrostructure: Catalogue · tone: modern-minimal · anchor hue: cobalt */",
             "/* Hallmark · pre-emit critique: P4 H5 E4 S5 R5 V4 */",
             "/* Native app consumes pdf_lover/ui/theme.py; this is its portable web token export. */", ":root {"]
    for name, (lightness, chroma, hue) in PALETTE.items():
        lines.append(f"  --color-{name}: oklch({lightness * 100:g}% {chroma:g} {hue:g});")
    for name, face in FONTS.items():
        lines.append(f'  --font-{name}: "{face}", sans-serif;')
    for name, value in SPACE.items():
        lines.append(f"  --space-{name}: {value}px;")
    for name, value in RADIUS.items():
        lines.append(f"  --radius-{name}: {value}px;")
    lines.extend(["  --text-sm: 14px;", "  --text-md: 16px;", "  --text-display: 28px;",
                  "  --rule-width: 1px;", "  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);",
                  "  --ease-in: cubic-bezier(0.7, 0, 0.84, 0);",
                  "  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);", "  --dur-micro: 120ms;", "}"])
    return "\n".join(lines) + "\n"
