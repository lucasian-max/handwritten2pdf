#!/usr/bin/env python3
"""Generate a synthetic 'handwritten lecture note' page as SVG, then rasterize.

Used as a test fixture for the handwriting->LaTeX pipeline. No external deps.
"""

import random
import subprocess
import sys

random.seed(7)

W, H = 1000, 1414  # A4-ish ratio
INK = "#1a3fa0"  # blue ink
PENCIL = "#333333"
LINE = "#cfe0f0"  # ruled lines
MARGIN = "#e8a0a0"


def jitter(x, y, s=1.5):
    return x + random.uniform(-s, s), y + random.uniform(-s, s)


def word(text, x, y, size, font="Z003", fill=INK, rot=None, italic=False):
    """Emit a <text> with slight rotation and baseline jitter."""
    if rot is None:
        rot = random.uniform(-2.5, 2.5)
    tx, ty = jitter(x, y, 0.8)
    return (
        f'<text x="{tx:.1f}" y="{ty:.1f}" font-family="{font}" '
        f'font-size="{size}" fill="{fill}" transform="rotate({rot:.2f} {tx:.1f} {ty:.1f})">'
        f"{text}</text>"
    )


def equation(text, x, y, size=30):
    """Math in a plainer font so the vision model reads it cleanly."""
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

# ruled paper lines
for ly in range(140, H - 60, 62):
    parts.append(
        f'<line x1="40" y1="{ly}" x2="{W - 40}" y2="{ly}" stroke="{LINE}" stroke-width="1.2"/>'
    )
# margin line
parts.append(f'<line x1="86" y1="90" x2="86" y2="{H - 50}" stroke="{MARGIN}" stroke-width="1.5"/>')

# title, underlined with a wobbly hand line
parts.append(word("Gauss's Law", 150, 120, 58))
parts.append('<path d="M150,138 q120,8 290,2" stroke="#1a3fa0" stroke-width="2.5" fill="none"/>')

y = 210
parts.append(word("Electric flux through a closed", 110, y, 34))
parts.append(word("surface S:", 110, y + 44, 34))
y += 108
parts.append(equation("&#934;E  =  &#8751;S  E &#183; dA", 190, y, 38))
y += 92
parts.append(word("Field of a point charge q,", 110, y, 34))
parts.append(word("sphere of radius r around q:", 110, y + 44, 34))
y += 108
parts.append(equation("E  =  q / (4&#960;&#603;&#8320; r&#178;)", 200, y, 36))
y += 92

# hand-drawn diagram: sphere with radius r, field arrows E
cx, cy, rr = 250, y + 130, 90
parts.append(
    f'<circle cx="{cx}" cy="{cy}" r="{rr}" fill="none" stroke="{INK}" stroke-width="2.6"/>'
)
# radius arrow from center
rx, ry2 = cx + rr * 0.72, cy - rr * 0.72
parts.append(
    f'<line x1="{cx}" y1="{cy}" x2="{rx:.0f}" y2="{ry2:.0f}" stroke="{INK}" stroke-width="2"/>'
)
parts.append(
    f'<polygon points="{rx + 8:.0f},{ry2:.0f} {rx - 4:.0f},{ry2 - 3:.0f} {rx - 2:.0f},{ry2 + 9:.0f}" fill="{INK}"/>'
)
parts.append(word("r", (cx + rx) / 2 + 6, (cy + ry2) / 2 - 6, 30))
parts.append(word("q", cx - 10, cy + 34, 30))
# outward field arrow E
ax, ay = cx + 40, cy - rr - 90
parts.append(
    f'<line x1="{ax:.0f}" y1="{ay:.0f}" x2="{ax + 95:.0f}" y2="{ay - 25:.0f}" stroke="{INK}" stroke-width="2.4"/>'
)
parts.append(
    f'<polygon points="{ax + 104:.0f},{ay - 27:.0f} {ax + 90:.0f},{ay - 34:.0f} {ax + 94:.0f},{ay - 17:.0f}" fill="{INK}"/>'
)
parts.append(word("E", ax + 112, ay - 22, 30))
parts.append(word("S", cx + rr + 14, cy + 12, 28))

# derivation next to the diagram
dy = y + 90
parts.append(word("Flux through S:", 470, dy, 34))
parts.append(equation("&#934;E = E&#183;4&#960;r&#178;", 470, dy + 62, 33))
parts.append(equation("= (q/4&#960;&#603;&#8320;r&#178;) &#183; 4&#960;r&#178;", 470, dy + 122, 33))
parts.append(equation("= q&#8339;&#8345;&#8342; / &#603;&#8320;", 470, dy + 182, 36))
y = dy + 260

parts.append(word("Flux depends only on the charge", 110, y, 34))
parts.append(word("enclosed by S - not on r!", 110, y + 44, 34))
y += 108
parts.append(word("Note: works for any closed", 110, y, 34))
parts.append(word("surface around q (no sharp", 110, y + 44, 34))
parts.append(word("corners needed).", 110, y + 88, 34))

parts.append("</svg>")

svg = "\n".join(parts)
out_svg = sys.argv[1] if len(sys.argv) > 1 else "hw_page.svg"
out_png = out_svg.replace(".svg", ".png")
with open(out_svg, "w") as f:
    f.write(svg)
subprocess.run(["rsvg-convert", "-w", "1400", "-o", out_png, out_svg], check=True)
print("wrote", out_png)
