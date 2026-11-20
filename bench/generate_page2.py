#!/usr/bin/env python3
"""Second synthetic 'handwritten lecture note' page: integration by parts."""

import random
import subprocess
import sys

random.seed(11)

W, H = 1000, 1414
INK = "#1a3fa0"
LINE = "#cfe0f0"
MARGIN = "#e8a0a0"


def jitter(x, y, s=1.5):
    return x + random.uniform(-s, s), y + random.uniform(-s, s)


def word(text, x, y, size, fill=INK, rot=None):
    if rot is None:
        rot = random.uniform(-2.5, 2.5)
    tx, ty = jitter(x, y, 0.8)
    return (
        f'<text x="{tx:.1f}" y="{ty:.1f}" font-family="Z003" '
        f'font-size="{size}" fill="{fill}" transform="rotate({rot:.2f} {tx:.1f} {ty:.1f})">'
        f"{text}</text>"
    )


def eq(text, x, y, size=30):
    tx, ty = jitter(x, y, 0.6)
    rot = random.uniform(-1.2, 1.2)
    return (
        f'<text x="{tx:.1f}" y="{ty:.1f}" font-family="Nimbus Roman" '
        f'font-size="{size}" fill="{INK}" font-style="italic" '
        f'transform="rotate({rot:.2f} {tx:.1f} {ty:.1f})">{text}</text>'
    )


parts = []
parts.append(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
)
parts.append(f'<rect width="{W}" height="{H}" fill="#faf8f2"/>')
for ly in range(140, H - 60, 62):
    parts.append(
        f'<line x1="40" y1="{ly}" x2="{W - 40}" y2="{ly}" stroke="{LINE}" stroke-width="1.2"/>'
    )
parts.append(f'<line x1="86" y1="90" x2="86" y2="{H - 50}" stroke="{MARGIN}" stroke-width="1.5"/>')

parts.append(word("Integration by Parts", 130, 120, 56))
parts.append('<path d="M130,140 q150,8 380,2" stroke="#1a3fa0" stroke-width="2.5" fill="none"/>')

y = 210
parts.append(word("From the product rule for", 110, y, 34))
parts.append(word("derivatives:", 110, y + 44, 34))
y += 108
parts.append(eq("(uv)&#8242;  =  u&#8242;v + uv&#8242;", 220, y, 36))
y += 92
parts.append(word("Integrate both sides, move", 110, y, 34))
parts.append(word("one term across:", 110, y + 44, 34))
y += 108
parts.append(eq("&#8747; u dv  =  uv &#8722; &#8747; v du", 190, y, 38))
y += 100
parts.append(word("Example. Take", 110, y, 34))
parts.append(eq("&#8747; x e&#7491; dx", 110, y + 48, 34))
y += 96
parts.append(word("choose u = x, dv = e&#7491;dx", 150, y, 34))
y += 62
parts.append(word("then du = dx, v = e&#7491;", 150, y, 34))
y += 92
parts.append(eq("&#8747; x e&#7491; dx  =  x e&#7491; &#8722; &#8747; e&#7491; dx", 170, y, 34))
y += 80
parts.append(eq("= (x &#8722; 1) e&#7491; + C", 260, y, 36))
y += 92
parts.append(word("Check: differentiate the", 110, y, 34))
parts.append(word("answer - you get x e&#7491; back.", 110, y + 44, 34))

# small sketch: y = x e^x curve
cx, cy = 700, 700
parts.append(
    f'<line x1="{cx}" y1="{cy + 150}" x2="{cx + 230}" y2="{cy + 150}" stroke="{INK}" stroke-width="2.2"/>'
)
parts.append(
    f'<line x1="{cx}" y1="{cy + 170}" x2="{cx}" y2="{cy - 190}" stroke="{INK}" stroke-width="2.2"/>'
)
parts.append(
    f'<polygon points="{cx + 4},{cy - 178} {cx - 5},{cy - 162} {cx + 9},{cy - 166}" fill="{INK}"/>'
)
parts.append(word("y = x e&#7491;", cx + 130, cy - 150, 30))
parts.append(
    f'<path d="M {cx},{cy + 150} C {cx + 90},{cy + 90} {cx + 150},{cy - 10} {cx + 210},{cy - 170}" fill="none" stroke="{INK}" stroke-width="2.6"/>'
)
parts.append(word("x", cx + 225, cy + 175, 28))
parts.append(word("y", cx - 28, cy - 175, 28))

parts.append("</svg>")

svg = "\n".join(parts)
out_svg = sys.argv[1] if len(sys.argv) > 1 else "hw_page2.svg"
out_png = out_svg.replace(".svg", ".png")
with open(out_svg, "w") as f:
    f.write(svg)
subprocess.run(["rsvg-convert", "-w", "1400", "-o", out_png, out_svg], check=True)
print("wrote", out_png)
