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

# Everything on the page comes from the lists below. Run this script again after changing them.

# Newest app first: the cards follow this order. With an odd number of apps the newest one gets the wide card.
APPS = [
    dict(slug="gillow", name="Gillow", category="Health", status="In development",
         problem="Busy days make it easy to fall behind on water.",
         answer="Drink logging and reminders, with Gil the axolotl for company.",
         link="https://gillow.binerlabs.com/", colours=("#11868F", "#0A5566"), ink="#FFFFFF", mascot=238),
    dict(slug="lightjar", name="Lightjar", category="Wellbeing", status="Coming soon",
         problem="Stress and endless scrolling can leave you needing a lift.",
         answer="Short, kind quotes picked for how you feel, right on your Home Screen.",
         link="https://lightjar.binerlabs.com/", colours=("#323873", "#12152F"), ink="#FFFFFF", mascot=226),
    dict(slug="runbloom", name="Runbloom", category="Fitness", status="Coming soon",
         problem="Keeping a running habit going is hard once the first excitement fades.",
         answer="Every run grows a plant, so you can watch your progress become a garden.",
         link="https://runbloom.binerlabs.com/", colours=("#218A4B", "#125634"), ink="#FFFFFF", mascot=222),
    dict(slug="hypedeck", name="HypeDeck", category="Party game", status="Coming soon",
         problem="A get-together needs a game anyone can join right away.",
         answer="Charades on your forehead, with themed decks and a ticking clock.",
         link="https://hypedeck.binerlabs.com/", colours=("#FFD447", "#FFAA1D"), ink="#2E1F00", mascot=218),
    dict(slug="raftly", name="Raftly", category="Relationships", status="Coming soon",
         problem="Busy weeks crowd out real conversations between partners.",
         answer="One question a day for both of you, and a private thread to talk it over.",
         link="https://raftly.binerlabs.com/", colours=("#BC454D", "#85262F"), ink="#FFFFFF", mascot=212),
]
# Left to right in the banner. Every slug in APPS goes here too.
BANNER = ["hypedeck", "raftly", "gillow", "runbloom", "lightjar"]

# Counted from the app repositories on 2026-11-25. Recount before changing them.
STATS = [
    (str(len(APPS)), "products in the portfolio"),
    ("50", "App Store locales"),
    ("500+", "automated tests"),
    ("3 days", "fastest first commit to release build"),
]
STAGES = [
    ("Problem", "Pick something people struggle with."),
    ("Design", "Shape the look, voice and flow."),
    ("Build", "Write it in native Swift, with its backend."),
    ("Test", "Audit it and run automated tests."),
    ("Launch", "Set up cloud, payments and the release."),
    ("Localize", "Translate app and listing into 50 locales."),
]
HEADLINE = "We build products that solve everyday problems"
INTRO = ("Biner Labs is a software factory focused on native Apple apps. Each product starts with a problem "
         "people run into and goes through one shared production pipeline, so what we learn on one carries "
         "into the next. Today we build for iPhone and iPad in Swift and SwiftUI.")
PROCESS = ("Every product follows the same 22 steps, from the first brief to App Store listings. "
           "A release has to pass automated tests before it goes out.")
FOUNDER = ("ranggabiner", "https://github.com/ranggabiner")
NARROW = "(max-width: 700px)"


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

    def width(self, text, size, tracking=0):
        advances = [p.x_advance for p in self.shape(text)[1]]
        return sum(advances) * size / self.upm + tracking * (len(advances) - 1)

    def path(self, text, x, y, size, fill, opacity=1, tracking=0):
        scale = size / self.upm
        pen = SVGPathPen(self.glyphs, ntos=num)
        for info, pos in zip(*self.shape(text)):
            moved = TransformPen(pen, (scale, 0, 0, -scale, x + pos.x_offset * scale, y - pos.y_offset * scale))
            self.glyphs[self.order[info.codepoint]].draw(moved)
            x += pos.x_advance * scale + tracking
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

    def centred(self, text, middle, y, size, fill, opacity=1, tracking=0):
        return self.path(text, middle - self.width(text, size, tracking) / 2, y, size, fill, opacity, tracking)

    def fit(self, text, size, limit, lines):
        wrapped = self.wrap(text, size, limit)
        if len(wrapped) > lines:
            raise ValueError(f"Too long for {lines} lines: {text}")
        return wrapped


def png(name):
    data = (ART / name).read_bytes()
    width, height = struct.unpack(">II", data[16:24])
    return "data:image/png;base64," + base64.b64encode(data).decode(), width, height


def svg(width, height, label, body, pad_x=0, pad_y=0):
    outer_w, outer_h = width + 2 * pad_x, height + 2 * pad_y
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad_x} {-pad_y} {outer_w} {outer_h}" '
            f'width="{outer_w}" height="{outer_h}" role="img"><title>{html.escape(label)}</title>{body}</svg>\n')


def banner(bold, light, medium, narrow):
    width, height = (836, 600) if narrow else (1280, 500)
    floor = height - 42
    size, baseline = (112, 150) if narrow else (100, 126)
    total = bold.width("BINER", size) + light.width("LABS", size)
    left = (width - total) / 2
    words = bold.path("BINER", left, baseline, size, "#FFFFFF") + light.path(
        "LABS", left + bold.width("BINER", size), baseline, size, "#FFFFFF")
    if narrow:
        words += medium.centred("SOFTWARE FACTORY", width / 2, 218, 38, "#BFDDFF", tracking=6)
        words += medium.centred("FOR APPLE PLATFORMS", width / 2, 272, 38, "#BFDDFF", tracking=6)
    else:
        words += medium.centred("SOFTWARE FACTORY FOR APPLE PLATFORMS", width / 2, 180, 25, "#BFDDFF", tracking=6)

    heights = {app["slug"]: app["mascot"] for app in APPS}
    scale, margin = (0.66, 26) if narrow else (1, 50)
    sprites = []
    for slug in BANNER:
        uri, w, h = png(f"{slug}-mascot.png")
        tall = heights[slug] * scale
        sprites.append((uri, w * tall / h, tall))
    gap = (width - 2 * margin - sum(s[1] for s in sprites)) / (len(sprites) - 1)
    x, shadows, mascots = margin, "", ""
    for index, (uri, w, h) in enumerate(sprites):
        delay = num(-0.65 * index)
        shadows += (f'<ellipse class="shadow" style="animation-delay:{delay}s" cx="{num(x + w / 2)}" cy="{floor + 6}" '
                    f'rx="{num(w * 0.34)}" ry="9" fill="#000" fill-opacity=".5"/>')
        mascots += (f'<g class="bob" style="animation-delay:{delay}s"><image href="{uri}" x="{num(x)}" '
                    f'y="{num(floor - h)}" width="{num(w)}" height="{num(h)}"/></g>')
        x += w + gap

    stars = ""
    for index, (sx, sy, r) in enumerate([(188, 96, 13), (322, 150, 7), (226, 216, 5), (1010, 70, 8),
                                          (1130, 150, 13), (930, 222, 5), (110, 180, 6)]):
        sx = round(sx * width / 1280)
        stars += (f'<path class="twinkle" style="animation-delay:{num(-0.45 * index)}s" fill="#CDE6FF" '
                  f'd="M{sx} {sy - r}Q{sx} {sy} {sx + r} {sy}Q{sx} {sy} {sx} {sy + r}'
                  f'Q{sx} {sy} {sx - r} {sy}Q{sx} {sy} {sx} {sy - r}Z"/>')

    body = f"""<style>
.bob{{animation:bob 3.2s ease-in-out infinite}}
.shadow{{animation:shadow 3.2s ease-in-out infinite;transform-box:fill-box;transform-origin:center}}
.twinkle{{animation:twinkle 3.6s ease-in-out infinite;transform-box:fill-box;transform-origin:center}}
.glow-a{{animation:drift-a 11s ease-in-out infinite alternate}}
.glow-b{{animation:drift-b 13s ease-in-out infinite alternate}}
@keyframes bob{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-14px)}}}}
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
<circle class="glow-b" cx="{width - 20}" cy="{height + 10}" r="360" fill="url(#blue-b)"/>
{stars}{words}{shadows}{mascots}</g>"""
    return svg(width, height, "Biner Labs. A software factory for Apple platforms.", body)


def panel(x, y, width, height):
    return (f'<rect x="{num(x)}" y="{num(y)}" width="{num(width)}" height="{num(height)}" rx="32" fill="url(#navy)" '
            'stroke="#32639C" stroke-width="2"/>')


NAVY = ('<defs><linearGradient id="navy" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1B375C"/>'
        '<stop offset="1" stop-color="#070F1C"/></linearGradient></defs>')


def stats(bold, medium, narrow):
    columns = 2 if narrow else len(STATS)
    width, gap, tall = (820 if narrow else 1664), 16, 222
    across = (width - gap * (columns - 1)) / columns
    rows = (len(STATS) + columns - 1) // columns
    body = NAVY
    for index, (value, label) in enumerate(STATS):
        x, y = (index % columns) * (across + gap), (index // columns) * (tall + gap)
        middle = x + across / 2
        lines = medium.fit(label, 28, across - 48, 2)
        body += panel(x + 1, y + 1, across - 2, tall - 2) + bold.centred(value, middle, y + 106, 84, "#FFFFFF")
        for row, line in enumerate(lines):
            body += medium.centred(line, middle, y + 154 + 36 * row, 28, "#A9CFF7")
    label = ". ".join(f"{value} {text}" for value, text in STATS)
    return svg(width, rows * tall + gap * (rows - 1), label, body, pad_x=8, pad_y=4)


def pipeline(bold, medium, narrow):
    body = NAVY
    motion = "translate(0,660px)" if narrow else "translate(1386.7px,0)"
    body += ('<style>.pulse{animation:flow 7s linear infinite}'
             f'@keyframes flow{{0%{{transform:translate(0,0);opacity:0}}8%,92%{{opacity:1}}100%{{transform:{motion};opacity:0}}}}'
             '@media (prefers-reduced-motion:reduce){.pulse{display:none}}</style>')
    if narrow:
        width, height, step = 820, 132 * len(STAGES) + 16, 132
        body += panel(1, 1, width - 2, height - 2)
        body += f'<path d="M76 74V{74 + step * (len(STAGES) - 1)}" stroke="#3F78B8" stroke-width="4"/>'
        body += '<circle class="pulse" cx="76" cy="74" r="11" fill="#9FD0FF"/>'
    else:
        width, height = 1664, 306
        column = width / len(STAGES)
        body += panel(1, 1, width - 2, height - 2)
        body += f'<path d="M{num(column / 2)} 78H{num(width - column / 2)}" stroke="#3F78B8" stroke-width="4"/>'
        body += f'<circle class="pulse" cx="{num(column / 2)}" cy="78" r="11" fill="#9FD0FF"/>'
    for index, (title, text) in enumerate(STAGES):
        x, y = (76, 74 + 132 * index) if narrow else (width / len(STAGES) * (index + 0.5), 78)
        body += f'<circle cx="{num(x)}" cy="{y}" r="36" fill="#12294A" stroke="#6FB2FF" stroke-width="3"/>'
        body += bold.centred(str(index + 1), x, y + 11, 31, "#FFFFFF")
        if narrow:
            body += bold.path(title, 144, y - 8, 36, "#FFFFFF")
            body += medium.path(medium.fit(text, 28, 640, 1)[0], 144, y + 34, 28, "#A9CFF7")
        else:
            body += bold.centred(title, x, 166, 31, "#FFFFFF")
            for row, line in enumerate(medium.fit(text, 24, width / len(STAGES) - 28, 3)):
                body += medium.centred(line, x, 208 + 32 * row, 24, "#A9CFF7")
    label = " ".join(f"{index + 1}. {title}: {text}" for index, (title, text) in enumerate(STAGES))
    return svg(width, height, label, body, pad_x=8, pad_y=4)


def arrow(x, ink):
    return (f'<path d="M{x} 62l24-24m-20 0h20v20" fill="none" stroke="{ink}" stroke-opacity=".75" '
            'stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>')


def icon(slug, x, y, size, ink):
    box = f'x="{x}" y="{y}" width="{size}" height="{size}"'
    radius = round(size * 0.233)
    return (f'<clipPath id="icon"><rect {box} rx="{radius}"/></clipPath>'
            f'<image href="{png(f"{slug}-icon.png")[0]}" {box} clip-path="url(#icon)"/>'
            f'<rect {box} rx="{radius}" fill="none" stroke="{ink}" stroke-opacity=".22" stroke-width="3"/>')


def pills(bold, labels, x, y, ink):
    drawn = ""
    for label in labels:
        text = label.upper()
        across = bold.width(text, 20, 1) + 34
        drawn += (f'<rect x="{num(x)}" y="{y}" width="{num(across)}" height="40" rx="20" fill="{ink}" fill-opacity=".16"/>'
                  + bold.path(text, x + 17, y + 27, 20, ink, tracking=1))
        x += across + 10
    return drawn


def passage(bold, medium, title, text, x, y, limit, ink):
    drawn = bold.path(title, x, y, 21, ink, 0.72, tracking=3)
    for row, line in enumerate(medium.fit(text, 31, limit, 2)):
        drawn += medium.path(line, x, y + 44 + 42 * row, 31, ink)
    return drawn


def tile(width, height, label, colours, content, style=""):
    body = (f'{style}<defs><linearGradient id="fill" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{colours[0]}"/>'
            f'<stop offset="1" stop-color="{colours[1]}"/></linearGradient>'
            f'<clipPath id="frame"><rect width="{width}" height="{height}" rx="36"/></clipPath></defs>'
            f'<g clip-path="url(#frame)"><rect width="{width}" height="{height}" fill="url(#fill)"/>'
            f'<circle cx="{width - 50}" cy="{height + 28}" r="150" fill="#FFF" fill-opacity=".08"/>'
            f'<circle cx="{width - 160}" cy="{height + 58}" r="110" fill="#FFF" fill-opacity=".06"/>'
            f'{content}</g>')
    return svg(width, height, label, body, pad_x=8, pad_y=4)


def describe(app):
    return (f'{app["name"]} ({app["category"]}, {app["status"].lower()}). '
            f'Problem: {app["problem"]} Our answer: {app["answer"]}')


def card(bold, medium, app, newest):
    ink = app["ink"]
    labels = [app["category"], app["status"]]
    content = (icon(app["slug"], 40, 40, 140, ink) + bold.path(app["name"], 212, 100, 52, ink)
               + pills(bold, labels, 212, 126, ink) + arrow(756, ink)
               + passage(bold, medium, "PROBLEM", app["problem"], 40, 236, 740, ink)
               + passage(bold, medium, "OUR ANSWER", app["answer"], 40, 372, 740, ink))
    return tile(820, 490, describe(app), app["colours"], content)


def wide_card(bold, medium, app):
    width, height, ink = 1664, 400, app["ink"]
    mascot, w, h = png(f'{app["slug"]}-mascot.png')
    tall = 318
    across = w * tall / h
    left = width - across - 84
    column = (left - 46 - 40) / 2
    labels = ["Newest", app["category"], app["status"]]
    friend = (f'<ellipse cx="{num(left + across / 2)}" cy="{height - 24}" rx="{num(across * 0.32)}" ry="9" fill="#000" fill-opacity=".28"/>'
              f'<g class="bob"><image href="{mascot}" x="{num(left)}" y="{height - tall - 28}" width="{num(across)}" height="{tall}"/></g>')
    style = ('<style>.bob{animation:bob 3.2s ease-in-out infinite}'
             '@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-12px)}}'
             '@media (prefers-reduced-motion:reduce){.bob{animation:none}}</style>')
    content = (icon(app["slug"], 46, 44, 148, ink) + bold.path(app["name"], 228, 108, 62, ink)
               + pills(bold, labels, 228, 136, ink) + friend + arrow(width - 64, ink)
               + passage(bold, medium, "PROBLEM", app["problem"], 46, 262, column - 30, ink)
               + passage(bold, medium, "OUR ANSWER", app["answer"], 46 + column + 20, 262, column, ink))
    return tile(width, height, describe(app), app["colours"], content, style)


def publish(name, content):
    """Writes one asset and returns its URL, versioned so a change shows up despite caching."""
    (OUT / name).write_text(content)
    return f"{RAW}/{name}?v={hashlib.sha1(content.encode()).hexdigest()[:8]}"


def responsive(wide, narrow, width, label):
    """A picture that swaps to a taller layout on phone-sized screens."""
    return (f'<picture><source media="{NARROW}" srcset="{narrow}">'
            f'<img src="{wide}" width="{width}" alt="{html.escape(label)}"></picture>')


def centred(content, tag="p"):
    return f'<{tag} align="center">\n  {content}\n</{tag}>'


def main():
    font = sys.argv[1]
    bold, light, medium = Face(font, 800), Face(font, 300), Face(font, 600)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()

    names = ", ".join(a["name"] for a in APPS[:-1]) + f' and {APPS[-1]["name"]}'
    top = responsive(publish("banner.svg", banner(bold, light, medium, False)),
                     publish("banner-narrow.svg", banner(bold, light, medium, True)), "100%",
                     f"Biner Labs, a software factory for Apple platforms, with the mascots of {names}")
    numbers = responsive(publish("stats.svg", stats(bold, medium, False)),
                         publish("stats-narrow.svg", stats(bold, medium, True)), 824,
                         ". ".join(f"{value} {text}" for value, text in STATS))
    steps = responsive(publish("pipeline.svg", pipeline(bold, medium, False)),
                       publish("pipeline-narrow.svg", pipeline(bold, medium, True)), 824,
                       "How the factory works: " + ", ".join(title for title, _ in STAGES))

    cards = []
    for position, app in enumerate(APPS):
        newest = position == 0 and len(APPS) % 2 == 1
        small = publish(f'card-{app["slug"]}.svg', card(bold, medium, app, newest))
        if newest:
            wide = publish(f'card-{app["slug"]}-wide.svg', wide_card(bold, medium, app))
            image = responsive(wide, small, 824, describe(app))
        else:
            image = f'<img src="{small}" width="410" alt="{html.escape(describe(app))}">'
        cards.append(f'<a href="{app["link"]}">{image}</a>')

    sections = [
        centred(top),
        centred(HEADLINE, "h2"),
        centred(INTRO),
        centred(numbers),
        centred("Portfolio", "h3"),
        centred("\n  ".join(cards)),
        centred("How the factory works", "h3"),
        centred(steps),
        centred(PROCESS),
        centred(f'<a href="{FOUNDER[1]}"><b>{FOUNDER[0]}</b></a>'),
    ]
    (ROOT / "profile" / "README.md").write_text("\n\n".join(sections) + "\n")


if __name__ == "__main__":
    main()
