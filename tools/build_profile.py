"""Builds profile/README.md and its SVG art.

Usage: python3 tools/build_profile.py path/to/Montserrat[wght].ttf
Needs fonttools and uharfbuzz.

To add an app, put <slug>-mascot.png (transparent) and <slug>-icon.png (square)
in tools/art/, add a row to APPS, and run this again.
"""
import base64
import html
import io
import struct
import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "tools" / "art"
OUT = ROOT / "profile" / "assets"
RAW = "https://raw.githubusercontent.com/binerlabs/.github/main/profile/assets"

# slug, name, tagline, website (None until it is ready), card colours, text colour, banner mascot height
APPS = [
    ("hypedeck", "HypeDeck", "Charades on your forehead. Guess the card before time runs out.",
     "https://hypedeck.binerlabs.com/", ("#FFD447", "#FFAA1D"), "#2E1F00", 218),
    ("raftly", "Raftly", "One question a day for you and your partner.",
     "https://raftly.binerlabs.com/", ("#BC454D", "#85262F"), "#FFFFFF", 212),
    ("gillow", "Gillow", "A water tracker with Gil, a friendly axolotl.",
     None, ("#11868F", "#0A5566"), "#FFFFFF", 238),
    ("runbloom", "Runbloom", "Every run grows a plant in your own garden.",
     "https://runbloom.binerlabs.com/", ("#218A4B", "#125634"), "#FFFFFF", 222),
    ("lightjar", "Lightjar", "Short, kind quotes picked for how you feel.",
     "https://lightjar.binerlabs.com/", ("#323873", "#12152F"), "#FFFFFF", 226),
]
CREDIT = ("credit", "rangga & claude", "We make all of these in Swift and SwiftUI.")


def num(value):
    return f"{value:.1f}".rstrip("0").rstrip(".")


class Face:
    """One weight of the font, drawn as outlines so every viewer sees the same text."""

    def __init__(self, path, weight):
        buffer = io.BytesIO()
        instantiateVariableFont(TTFont(path), {"wght": weight}).save(buffer)
        data = buffer.getvalue()
        self.font = TTFont(io.BytesIO(data))
        self.shaper = hb.Font(hb.Face(data))
        self.upm = self.font["head"].unitsPerEm
        self.glyphs = self.font.getGlyphSet()
        self.order = self.font.getGlyphOrder()

    def shape(self, text):
        buffer = hb.Buffer()
        buffer.add_str(text)
        buffer.guess_segment_properties()
        hb.shape(self.shaper, buffer)
        return buffer.glyph_infos, buffer.glyph_positions

    def width(self, text, size):
        return sum(p.x_advance for p in self.shape(text)[1]) * size / self.upm

    def path(self, text, x, y, size, fill, opacity=1):
        scale = size / self.upm
        pen = SVGPathPen(self.glyphs, ntos=num)
        for info, pos in zip(*self.shape(text)):
            moved = TransformPen(pen, (scale, 0, 0, -scale, x + pos.x_offset * scale, y - pos.y_offset * scale))
            self.glyphs[self.order[info.codepoint]].draw(moved)
            x += pos.x_advance * scale
        return f'<path fill="{fill}" fill-opacity="{opacity}" d="{pen.getCommands()}"/>'

    def wrap(self, text, size, limit):
        lines = [""]
        for word in text.split():
            trial = f"{lines[-1]} {word}".strip()
            if lines[-1] and self.width(trial, size) > limit:
                lines.append(word)
            else:
                lines[-1] = trial
        return lines


def png(name):
    data = (ART / name).read_bytes()
    width, height = struct.unpack(">II", data[16:24])
    return "data:image/png;base64," + base64.b64encode(data).decode(), width, height


def svg(width, height, label, body, pad_x=0, pad_y=0):
    outer_w, outer_h = width + 2 * pad_x, height + 2 * pad_y
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad_x} {-pad_y} {outer_w} {outer_h}" '
            f'width="{outer_w}" height="{outer_h}" role="img"><title>{html.escape(label)}</title>{body}</svg>\n')


def banner(bold, light):
    width, height, floor = 1280, 480, 438
    size = 100
    total = bold.width("BINER", size) + light.width("LABS", size)
    left = (width - total) / 2
    wordmark = bold.path("BINER", left, 138, size, "#FFFFFF") + light.path(
        "LABS", left + bold.width("BINER", size), 138, size, "#FFFFFF")

    sprites = []
    for slug, *_, tall in APPS:
        uri, w, h = png(f"{slug}-mascot.png")
        sprites.append((uri, w * tall / h, tall))
    gap = (width - 100 - sum(s[1] for s in sprites)) / (len(sprites) - 1)
    x, shadows, mascots = 50, "", ""
    for index, (uri, w, h) in enumerate(sprites):
        delay = num(-0.65 * index)
        shadows += (f'<ellipse class="shadow" style="animation-delay:{delay}s" cx="{num(x + w / 2)}" cy="{floor + 6}" '
                    f'rx="{num(w * 0.34)}" ry="9" fill="#000" fill-opacity=".5"/>')
        mascots += (f'<g class="bob" style="animation-delay:{delay}s"><image href="{uri}" x="{num(x)}" '
                    f'y="{floor - h}" width="{num(w)}" height="{h}"/></g>')
        x += w + gap

    stars = ""
    for index, (sx, sy, r) in enumerate([(188, 96, 13), (322, 168, 7), (226, 208, 5), (968, 74, 8),
                                          (1096, 150, 13), (904, 190, 5), (640, 188, 6)]):
        stars += (f'<path class="twinkle" style="animation-delay:{num(-0.45 * index)}s" fill="#CDE6FF" '
                  f'd="M{sx} {sy - r}Q{sx} {sy} {sx + r} {sy}Q{sx} {sy} {sx} {sy + r}'
                  f'Q{sx} {sy} {sx - r} {sy}Q{sx} {sy} {sx} {sy - r}Z"/>')

    body = f"""<style>
.bob{{animation:bob 3.2s ease-in-out infinite}}
.shadow{{animation:shadow 3.2s ease-in-out infinite;transform-box:fill-box;transform-origin:center}}
.twinkle{{animation:twinkle 3.6s ease-in-out infinite;transform-box:fill-box;transform-origin:center}}
.glow-a{{animation:drift-a 11s ease-in-out infinite alternate}}
.glow-b{{animation:drift-b 13s ease-in-out infinite alternate}}
@keyframes bob{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-16px)}}}}
@keyframes shadow{{0%,100%{{transform:scale(1);opacity:1}}50%{{transform:scale(.78);opacity:.6}}}}
@keyframes twinkle{{0%,100%{{opacity:.15;transform:scale(.6)}}50%{{opacity:1;transform:scale(1)}}}}
@keyframes drift-a{{to{{transform:translate(150px,60px)}}}}
@keyframes drift-b{{to{{transform:translate(-170px,-50px)}}}}
@media (prefers-reduced-motion:reduce){{.bob,.shadow,.twinkle,.glow-a,.glow-b{{animation:none}}}}
</style>
<defs>
<linearGradient id="sky" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2A507C"/><stop offset=".4" stop-color="#142945"/><stop offset=".75" stop-color="#08101D"/><stop offset="1" stop-color="#03060C"/></linearGradient>
<radialGradient id="blue-a"><stop offset="0" stop-color="#4F9AE6" stop-opacity=".8"/><stop offset="1" stop-color="#4F9AE6" stop-opacity="0"/></radialGradient>
<radialGradient id="blue-b"><stop offset="0" stop-color="#7BC0FF" stop-opacity=".75"/><stop offset="1" stop-color="#7BC0FF" stop-opacity="0"/></radialGradient>
<clipPath id="frame"><rect width="{width}" height="{height}" rx="36"/></clipPath>
</defs>
<g clip-path="url(#frame)"><rect width="{width}" height="{height}" fill="url(#sky)"/>
<circle class="glow-a" cx="40" cy="0" r="340" fill="url(#blue-a)"/>
<circle class="glow-b" cx="1260" cy="490" r="360" fill="url(#blue-b)"/>
{stars}{wordmark}{shadows}{mascots}</g>"""
    return svg(width, height, "Biner Labs", body)


def card(bold, medium, slug, name, tagline, link, colours, ink):
    width, height = 820, 272
    if slug == "credit":
        mark = '<rect x="40" y="46" width="180" height="180" rx="42" fill="#4F9AE6" fill-opacity=".28"/>'
        mark += bold.path("&", 130 - bold.width("&", 118) / 2, 177, 118, "#FFFFFF")
    else:
        uri = png(f"{slug}-icon.png")[0]
        mark = ('<clipPath id="icon"><rect x="40" y="46" width="180" height="180" rx="42"/></clipPath>'
                f'<image href="{uri}" x="40" y="46" width="180" height="180" clip-path="url(#icon)"/>'
                f'<rect x="40" y="46" width="180" height="180" rx="42" fill="none" stroke="{ink}" stroke-opacity=".22" stroke-width="3"/>')
    lines = medium.wrap(tagline, 31, 530)
    top = (height - (52 + 18 + 43 * len(lines))) / 2
    text = bold.path(name, 256, top + 46, 50, ink)
    for index, line in enumerate(lines):
        text += medium.path(line, 256, top + 104 + 43 * index, 31, ink, 0.92)
    arrow = (f'<path d="M756 62l24-24m-20 0h20v20" fill="none" stroke="{ink}" stroke-opacity=".75" '
             'stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>') if link else ""
    body = (f'<defs><linearGradient id="fill" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{colours[0]}"/>'
            f'<stop offset="1" stop-color="{colours[1]}"/></linearGradient>'
            f'<clipPath id="frame"><rect width="{width}" height="{height}" rx="36"/></clipPath></defs>'
            f'<g clip-path="url(#frame)"><rect width="{width}" height="{height}" fill="url(#fill)"/>'
            '<circle cx="770" cy="300" r="150" fill="#FFF" fill-opacity=".08"/>'
            '<circle cx="660" cy="330" r="110" fill="#FFF" fill-opacity=".06"/>'
            f'{mark}{text}{arrow}</g>')
    return svg(width, height, f"{name}. {tagline}", body, pad_x=8, pad_y=4)


def main():
    font = sys.argv[1]
    bold, light, medium = Face(font, 800), Face(font, 300), Face(font, 600)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "banner.svg").write_text(banner(bold, light))

    tiles = []
    credit = (*CREDIT, None, ("#1D3A60", "#060C18"), "#FFFFFF")
    for slug, name, tagline, link, colours, ink, *_ in [*APPS, credit]:
        (OUT / f"card-{slug}.svg").write_text(card(bold, medium, slug, name, tagline, link, colours, ink))
        image = f'<img src="{RAW}/card-{slug}.svg" width="410" alt="{html.escape(f"{name}. {tagline}")}">'
        tiles.append(f'<a href="{link}">{image}</a>' if link else image)

    names = ", ".join(a[1] for a in APPS[:-1]) + f" and {APPS[-1][1]}"
    readme = (f'<p align="center">\n  <img src="{RAW}/banner.svg" width="100%" '
              f'alt="Biner Labs, with the mascots of {names}">\n</p>\n\n'
              '<p align="center">\n  ' + "\n  ".join(tiles) + "\n</p>\n")
    (ROOT / "profile" / "README.md").write_text(readme)


if __name__ == "__main__":
    main()
