"""Builds profile/README.md and its SVG art.

Usage: python3 tools/build_profile.py path/to/Montserrat[wght].ttf
Needs fonttools and uharfbuzz.

To add an app, put <slug>-mascot.png (transparent) and <slug>-icon.png (square)
in tools/art/, add a row to APPS, and run this again.
"""
import base64
import hashlib
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

# Newest app first: the cards follow this order. With an odd number of apps the newest one gets the wide card.
# slug, name, tagline, website, card colours, text colour, banner mascot height
APPS = [
    ("gillow", "Gillow", "A water tracker with Gil, a friendly axolotl.",
     "https://gillow.binerlabs.com/", ("#11868F", "#0A5566"), "#FFFFFF", 238),
    ("lightjar", "Lightjar", "Short, kind quotes picked for how you feel.",
     "https://lightjar.binerlabs.com/", ("#323873", "#12152F"), "#FFFFFF", 226),
    ("runbloom", "Runbloom", "Every run grows a plant in your own garden.",
     "https://runbloom.binerlabs.com/", ("#218A4B", "#125634"), "#FFFFFF", 222),
    ("hypedeck", "HypeDeck", "A charades game you hold up to your forehead.",
     "https://hypedeck.binerlabs.com/", ("#FFD447", "#FFAA1D"), "#2E1F00", 218),
    ("raftly", "Raftly", "One question a day for you and your partner.",
     "https://raftly.binerlabs.com/", ("#BC454D", "#85262F"), "#FFFFFF", 212),
]
# Left to right in the banner. Every slug in APPS goes here too.
BANNER = ["hypedeck", "raftly", "gillow", "runbloom", "lightjar"]
SIGNATURE = "made by rangga &amp; claude"


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

    heights = {app[0]: app[-1] for app in APPS}
    sprites = []
    for slug in BANNER:
        uri, w, h = png(f"{slug}-mascot.png")
        sprites.append((uri, w * heights[slug] / h, heights[slug]))
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


def arrow(x, ink):
    return (f'<path d="M{x} 62l24-24m-20 0h20v20" fill="none" stroke="{ink}" stroke-opacity=".75" '
            'stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>')


def icon(slug, x, y, size, ink):
    box = f'x="{x}" y="{y}" width="{size}" height="{size}"'
    radius = round(size * 0.233)
    return (f'<clipPath id="icon"><rect {box} rx="{radius}"/></clipPath>'
            f'<image href="{png(f"{slug}-icon.png")[0]}" {box} clip-path="url(#icon)"/>'
            f'<rect {box} rx="{radius}" fill="none" stroke="{ink}" stroke-opacity=".22" stroke-width="3"/>')


def tile(width, height, label, colours, content, style=""):
    body = (f'{style}<defs><linearGradient id="fill" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{colours[0]}"/>'
            f'<stop offset="1" stop-color="{colours[1]}"/></linearGradient>'
            f'<clipPath id="frame"><rect width="{width}" height="{height}" rx="36"/></clipPath></defs>'
            f'<g clip-path="url(#frame)"><rect width="{width}" height="{height}" fill="url(#fill)"/>'
            f'<circle cx="{width - 50}" cy="{height + 28}" r="150" fill="#FFF" fill-opacity=".08"/>'
            f'<circle cx="{width - 160}" cy="{height + 58}" r="110" fill="#FFF" fill-opacity=".06"/>'
            f'{content}</g>')
    return svg(width, height, label, body, pad_x=8, pad_y=4)


def card(bold, medium, slug, name, tagline, colours, ink):
    height = 272
    lines = medium.wrap(tagline, 31, 530)
    top = (height - (70 + 43 * len(lines))) / 2
    text = bold.path(name, 256, top + 46, 50, ink)
    for index, line in enumerate(lines):
        text += medium.path(line, 256, top + 104 + 43 * index, 31, ink, 0.92)
    return tile(820, height, f"{name}. {tagline}", colours, icon(slug, 40, 46, 180, ink) + text + arrow(756, ink))


def wide_card(bold, medium, slug, name, tagline, colours, ink):
    width, height = 1664, 324
    mascot, w, h = png(f"{slug}-mascot.png")
    tall = 270
    across = w * tall / h
    left = width - across - 130
    lines = medium.wrap(tagline, 36, left - 390)
    top = (height - (150 + 50 * len(lines))) / 2
    badge = "NEWEST"
    text = (f'<rect x="326" y="{num(top)}" width="{num(bold.width(badge, 23) + 40)}" height="44" rx="22" '
            f'fill="{ink}" fill-opacity=".18"/>' + bold.path(badge, 346, top + 30, 23, ink))
    text += bold.path(name, 326, top + 114, 62, ink)
    for index, line in enumerate(lines):
        text += medium.path(line, 326, top + 172 + 50 * index, 36, ink, 0.92)
    friend = (f'<ellipse cx="{num(left + across / 2)}" cy="{height - 20}" rx="{num(across * 0.32)}" ry="8" fill="#000" fill-opacity=".28"/>'
              f'<g class="bob"><image href="{mascot}" x="{num(left)}" y="{height - tall - 24}" width="{num(across)}" height="{tall}"/></g>')
    style = ('<style>.bob{animation:bob 3.2s ease-in-out infinite}'
             '@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-12px)}}'
             '@media (prefers-reduced-motion:reduce){.bob{animation:none}}</style>')
    content = icon(slug, 46, 46, 232, ink) + text + friend + arrow(width - 64, ink)
    return tile(width, height, f"{name}. {tagline}", colours, content, style)


def publish(name, content):
    """Writes one asset and returns its URL, versioned so a change shows up despite caching."""
    (OUT / name).write_text(content)
    return f"{RAW}/{name}?v={hashlib.sha1(content.encode()).hexdigest()[:8]}"


def main():
    font = sys.argv[1]
    bold, light, medium = Face(font, 800), Face(font, 300), Face(font, 600)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()
    top = publish("banner.svg", banner(bold, light))

    tiles = []
    for position, (slug, name, tagline, link, colours, ink, _) in enumerate(APPS):
        label = html.escape(f"{name}. {tagline}")
        small = publish(f"card-{slug}.svg", card(bold, medium, slug, name, tagline, colours, ink))
        if position == 0 and len(APPS) % 2:
            wide = publish(f"card-{slug}-wide.svg", wide_card(bold, medium, slug, name, tagline, colours, ink))
            image = (f'<picture><source media="(max-width: 700px)" srcset="{small}">'
                     f'<img src="{wide}" width="824" alt="{label}"></picture>')
        else:
            image = f'<img src="{small}" width="410" alt="{label}">'
        tiles.append(f'<a href="{link}">{image}</a>')

    names = ", ".join(a[1] for a in APPS[:-1]) + f" and {APPS[-1][1]}"
    readme = (f'<p align="center">\n  <img src="{top}" width="100%" '
              f'alt="Biner Labs, with the mascots of {names}">\n</p>\n\n'
              '<p align="center">\n  ' + "\n  ".join(tiles) + "\n</p>\n\n"
              f'<p align="center"><sub>{SIGNATURE}</sub></p>\n')
    (ROOT / "profile" / "README.md").write_text(readme)


if __name__ == "__main__":
    main()
