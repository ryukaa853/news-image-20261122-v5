#!/usr/bin/env python3
"""news-image-20261122-v5: a newspaper front page for Sunday, 22 Nov 2026.

Draws one 1024x1024 PNG that sums up the day's world news: a masthead
with the date, a lead story on the COP31 collapse with a big-numeral
anchor, a "by the numbers" strip, eight more stories in a grid with a
small drawn pictogram each, and fourteen further stories in an
"also today" column. Twenty-three real stories in all, each checked
against reporting of 21-22 November 2026 (see SOURCES.md).

Pure Python standard library only: no network, no randomness, no wall
clock, so every run writes byte-identical output. Text is drawn with a
bitmap font defined in this file (5x7 glyphs, scaled up).

Run:  mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import os
import struct
import zlib

W = 1024
H = 1024

PAPER = (250, 244, 232)
INK = (26, 26, 26)
NAVY = (18, 36, 70)
NAVY_SOFT = (38, 62, 102)
RED = (168, 30, 30)
RED_DARK = (132, 22, 22)
GOLD = (178, 140, 52)
CREAM = (250, 244, 232)
RULE = (120, 110, 88)
GREY = (104, 98, 84)
SOFT = (233, 226, 208)
WHITE = (255, 255, 255)
SKY = (176, 204, 224)
LEAF = (74, 110, 66)


# ---------------------------------------------------------------- PNG writer
def _png_chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def write_png(path, width, height, rgb):
    """rgb is width*height*3 bytes. Writes a deterministic PNG."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    idat = zlib.compress(bytes(raw), 9)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(_png_chunk(b"IHDR", ihdr))
        fh.write(_png_chunk(b"IDAT", idat))
        fh.write(_png_chunk(b"IEND", b""))


# ------------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, width, height, bg):
        self.w = width
        self.h = height
        self.px = bytearray(bg) * (width * height)

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(color)

    def fill_rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def hline(self, x, y, w, color):
        self.fill_rect(x, y, w, 1, color)

    def vline(self, x, y, h, color):
        self.fill_rect(x, y, 1, h, color)

    def outline(self, x, y, w, h, color, t=1):
        self.fill_rect(x, y, w, t, color)
        self.fill_rect(x, y + h - t, w, t, color)
        self.fill_rect(x, y, t, h, color)
        self.fill_rect(x + w - t, y, t, h, color)

    def line(self, x0, y0, x1, y1, color):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def thick_line(self, x0, y0, x1, y1, color, t=2):
        half = t // 2
        for ox in range(-half, half + 1):
            for oy in range(-half, half + 1):
                self.line(x0 + ox, y0 + oy, x1 + ox, y1 + oy, color)

    def circle(self, cx, cy, r, color):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                    self.set(xx, yy, color)

    def ring(self, cx, cy, r, color, t=2):
        for yy in range(cy - r - 1, cy + r + 2):
            for xx in range(cx - r - 1, cx + r + 2):
                d2 = (xx - cx) ** 2 + (yy - cy) ** 2
                if (r - t) ** 2 < d2 <= r * r:
                    self.set(xx, yy, color)

    def triangle(self, x0, y0, x1, y1, x2, y2, color):
        xs = sorted([x0, x1, x2])
        ys = sorted([y0, y1, y2])
        for yy in range(ys[0], ys[2] + 1):
            for xx in range(xs[0], xs[2] + 1):
                d0 = (xx - x1) * (y2 - y1) - (yy - y1) * (x2 - x1)
                d1 = (xx - x2) * (y0 - y2) - (yy - y2) * (x0 - x2)
                d2 = (xx - x0) * (y1 - y0) - (yy - y0) * (x1 - x0)
                if (d0 >= 0 and d1 >= 0 and d2 >= 0) or \
                        (d0 <= 0 and d1 <= 0 and d2 <= 0):
                    self.set(xx, yy, color)


# ------------------------------------------------------------- bitmap font
# Each glyph is 7 rows of 5 cells, '#' = ink. Own design, drawn on a
# 5-wide grid: capitals fill rows 0-6, lowercase sit on rows 2-6 with
# ascenders reaching row 0 and descenders row 6.
FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#..##", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
}

FONT.update({
    "a": (".....", ".....", ".####", "....#", ".####", "#...#", ".####"),
    "b": ("#....", "#....", "####.", "#...#", "#...#", "#...#", "####."),
    "c": (".....", ".....", ".####", "#....", "#....", "#....", ".####"),
    "d": ("....#", "....#", ".####", "#...#", "#...#", "#...#", ".####"),
    "e": (".....", ".....", ".###.", "#...#", "#####", "#....", ".###."),
    "f": ("..##.", ".#...", ".#...", "####.", ".#...", ".#...", ".#..."),
    "g": (".....", ".....", ".####", "#...#", "#...#", ".####", "....#"),
    "h": ("#....", "#....", "####.", "#...#", "#...#", "#...#", "#...#"),
    "i": (".....", "..#..", ".....", ".##..", "..#..", "..#..", ".###."),
    "j": (".....", "...#.", ".....", "..##.", "...#.", "...#.", ".##.."),
    "k": ("#....", "#....", "#..#.", "#.#..", "##...", "#.#..", "#..#."),
    "l": (".##..", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "m": (".....", ".....", "##.#.", "#.#.#", "#.#.#", "#.#.#", "#.#.#"),
    "n": (".....", ".....", "####.", "#...#", "#...#", "#...#", "#...#"),
    "o": (".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###."),
    "p": (".....", ".....", "####.", "#...#", "#...#", "####.", "#...."),
    "q": (".....", ".....", ".####", "#...#", "#...#", ".####", "....#"),
    "r": (".....", ".....", "#.##.", "##..#", "#....", "#....", "#...."),
    "s": (".....", ".....", ".####", "#....", ".###.", "....#", "####."),
    "t": (".#...", ".#...", "####.", ".#...", ".#...", ".#...", "..##."),
    "u": (".....", ".....", "#...#", "#...#", "#...#", "#...#", ".####"),
    "v": (".....", ".....", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "w": (".....", ".....", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."),
    "x": (".....", ".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#"),
    "y": (".....", ".....", "#...#", "#...#", "#...#", ".####", "....#"),
    "z": (".....", ".....", "#####", "...#.", "..#..", ".#...", "#####"),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ",": (".....", ".....", ".....", ".....", ".....", ".##..", ".#..."),
    ":": (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    ";": (".....", ".##..", ".##..", ".....", ".##..", ".##..", ".#..."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    "?": (".###.", "#...#", "....#", "..##.", "..#..", ".....", "..#.."),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    '"': (".#.#.", ".#.#.", ".#.#.", ".....", ".....", ".....", "....."),
    "-": (".....", ".....", ".....", ".###.", ".....", ".....", "....."),
    "(": ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ")": (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
    "/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    "%": ("##...", "##..#", "...#.", "..#..", ".#...", "#..##", "...##"),
    "&": (".###.", "#...#", "#...#", ".##..", "#.#.#", "#..#.", ".##.#"),
    "+": (".....", "..#..", "..#..", ".###.", "..#..", "..#..", "....."),
    "=": (".....", ".....", ".####", ".....", ".####", ".....", "....."),
    "*": (".....", ".#.#.", ".###.", "#####", ".###.", ".#.#.", "....."),
    "[": (".###.", ".#...", ".#...", ".#...", ".#...", ".#...", ".###."),
    "]": (".###.", "...#.", "...#.", "...#.", "...#.", "...#.", ".###."),
    "_": (".....", ".....", ".....", ".....", ".....", ".....", "#####"),
    "$": ("..#..", ".####", "#.#.#", ".###.", "..#.#", "####.", "..#.."),
})


def text_width(text, scale):
    """Width in px of text at the given scale (6 units per glyph)."""
    return len(text) * 6 * scale


def draw_text(cv, x, y, text, scale, color):
    """Draw text at top-left (x, y); returns the x just past the text."""
    cx = x
    for ch in text:
        glyph = FONT.get(ch)
        if glyph is None:
            glyph = FONT["?"]
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits[col] == "#":
                    cv.fill_rect(cx + col * scale, y + row * scale,
                                 scale, scale, color)
        cx += 6 * scale
    return cx


def draw_text_centered(cv, cx, y, text, scale, color):
    w = text_width(text, scale)
    return draw_text(cv, cx - w // 2, y, text, scale, color)


def draw_text_right(cv, rx, y, text, scale, color):
    w = text_width(text, scale)
    return draw_text(cv, rx - w, y, text, scale, color)


def wrap_text(text, max_w, scale):
    """Greedy word wrap; returns a list of lines fitting max_w px."""
    words = text.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, scale) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(cv, x, y, text, max_w, scale, color, leading=None):
    """Draw wrapped text; returns the y just below the last line."""
    if leading is None:
        leading = 7 * scale + 2
    yy = y
    for line in wrap_text(text, max_w, scale):
        draw_text(cv, x, yy, line, scale, color)
        yy += leading
    return yy

# ---------------------------------------------------------------- pictograms
# Each draws a small 56x56 scene inside the box at (bx, by). Simple
# geometric shapes only: hulls, roofs, cups, flames, rings.
def icon_ship(cv, bx, by):
    cv.fill_rect(bx + 8, by + 34, 40, 8, NAVY)
    cv.triangle(bx + 48, by + 34, bx + 48, by + 42, bx + 56, by + 42, NAVY)
    cv.vline(bx + 27, by + 10, 24, NAVY)
    cv.triangle(bx + 28, by + 10, bx + 28, by + 18, bx + 40, by + 14, RED)
    cv.hline(bx + 6, by + 48, 44, NAVY)
    cv.hline(bx + 12, by + 52, 32, NAVY)


def icon_flats(cv, bx, by):
    cv.fill_rect(bx + 8, by + 14, 16, 34, INK)
    cv.fill_rect(bx + 30, by + 26, 16, 22, INK)
    cv.triangle(bx + 30, by + 26, bx + 38, by + 18, bx + 46, by + 26, INK)
    for wx in (11, 17):
        for wy in (18, 26, 34):
            cv.fill_rect(bx + wx, by + wy, 4, 4, PAPER)
    cv.fill_rect(bx + 33, by + 30, 4, 4, PAPER)
    cv.fill_rect(bx + 39, by + 38, 4, 4, PAPER)


def icon_shop(cv, bx, by):
    for i in range(4):
        col = RED if i % 2 == 0 else PAPER
        cv.fill_rect(bx + 8 + i * 10, by + 12, 10, 8, col)
    cv.outline(bx + 8, by + 12, 40, 36, INK, 2)
    cv.fill_rect(bx + 22, by + 30, 12, 18, INK)
    cv.fill_rect(bx + 12, by + 26, 6, 6, INK)
    cv.fill_rect(bx + 38, by + 26, 6, 6, INK)


def icon_missiles(cv, bx, by):
    for k in range(3):
        x0 = bx + 8 + k * 6
        y0 = by + 44 - k * 4
        x1 = bx + 34 + k * 6
        y1 = by + 12 - k * 2
        cv.thick_line(x0, y0, x1, y1, RED, 3)
        cv.triangle(x1, y1, x1 - 6, y1 + 2, x1 - 2, y1 + 6, RED)


def icon_ballot(cv, bx, by):
    cv.fill_rect(bx + 10, by + 28, 36, 20, NAVY)
    cv.fill_rect(bx + 18, by + 24, 20, 4, NAVY)
    cv.thick_line(bx + 14, by + 12, bx + 22, by + 22, LEAF, 3)
    cv.thick_line(bx + 22, by + 22, bx + 42, by + 4, LEAF, 3)


def icon_trophy(cv, bx, by):
    cv.fill_rect(bx + 20, by + 10, 16, 18, GOLD)
    cv.fill_rect(bx + 26, by + 28, 4, 8, GOLD)
    cv.fill_rect(bx + 18, by + 36, 20, 5, GOLD)
    cv.fill_rect(bx + 14, by + 12, 6, 10, GOLD)
    cv.fill_rect(bx + 36, by + 12, 6, 10, GOLD)
    cv.fill_rect(bx + 14, by + 12, 6, 3, PAPER)
    cv.fill_rect(bx + 36, by + 12, 6, 3, PAPER)


def icon_flame(cv, bx, by):
    cv.fill_rect(bx + 8, by + 34, 40, 14, INK)
    cv.fill_rect(bx + 12, by + 24, 6, 10, INK)
    cv.triangle(bx + 26, by + 8, bx + 18, by + 26, bx + 34, by + 26, RED)
    cv.triangle(bx + 26, by + 16, bx + 22, by + 26, bx + 30, by + 26, GOLD)


def icon_cuffs(cv, bx, by):
    cv.ring(bx + 16, by + 30, 9, INK, 3)
    cv.ring(bx + 40, by + 30, 9, INK, 3)
    cv.thick_line(bx + 24, by + 24, bx + 32, by + 24, INK, 3)
    cv.circle(bx + 16, by + 30, 3, PAPER)
    cv.circle(bx + 40, by + 30, 3, PAPER)


ICONS = [icon_ship, icon_flats, icon_shop, icon_missiles,
         icon_ballot, icon_trophy, icon_flame, icon_cuffs]

# ------------------------------------------------------------------- content
LEAD = {
    "kicker": "CLIMATE - ANTALYA, TURKEY",
    "headline": "COP31 ENDS WITH NO DEAL",
    "deck": "After two weeks of talks and two days of overtime, the EU and "
            "about 130 parties reject a draft that never mentions fossil "
            "fuels. The longest climate summit on record - and the first "
            "to end with no deal since Copenhagen in 2009.",
    "numeral": "130",
    "num_label": ("PARTIES REJECTED", "THE DRAFT"),
}

NUMBERS = [
    ("130", "PARTIES", "REJECTED DRAFT"),
    ("258", "HOUSE SEATS", "MOST SINCE 1992"),
    ("186", "DRONES LAUNCHED", "AT UKRAINE"),
    ("3.7%", "S&P 500 FALL", "ON FRIDAY"),
    ("720", "INDIA DECLARES", "720/9 VS NZ"),
]

GRID = [
    ("WAR - LIBYA", "UKRAINE SINKS RUSSIAN WARSHIP",
     "Kyiv says sea drones sank the corvette Merkury at Benghazi."),
    ("WAR - UKRAINE", "FLATS COLLAPSE IN STRIKE NEAR KYIV",
     "Drone flattens flats in Dymer; 4 killed, a boy pulled alive."),
    ("WAR - UKRAINE", "SUPERMARKET HIT IN VYSHNEVE",
     "Drone hits a grocery store near Kyiv; 3 killed, 15 hurt."),
    ("SECURITY - POLAND", "THREE RUSSIAN MISSILES CROSSED INTO POLAND",
     "All three were Russian Kh-101s, prosecutors say. NATO meets."),
    ("POLITICS - USA", "DEMOCRATS WIN HOUSE BY 258",
     "Hubbard beats Foxx by 330 votes in North Carolina after recount."),
    ("SPORT - TURIN, ITALY", "ALCARAZ WINS FIRST ATP FINALS TITLE",
     "Alcaraz beats world No. 1 Zverev 6-2, 7-6(7) in the Turin final."),
    ("MIDDLE EAST - BAHRAIN", "IRAN STRIKES HIT BAHRAIN SITE",
     "Iran hits a civilian site in Sitra; two hurt. Tankers also hit."),
    ("JUSTICE - MEXICO", "EL CHAPO ISIDRO CAPTURED",
     "Troops seize cartel boss Isidro Meza Flores in Guasave; 11 killed."),
]

ALSO = [
    "MARKETS: NIKKEI FELL 5.06% ON FRIDAY",
    "F1: VERSTAPPEN WINS LAS VEGAS GP",
    "CRICKET: INDIA LEAD NZ BY 352 RUNS",
    "NEPAL: PM SHAH ARRIVES IN INDIA",
    "JAPAN: SHURI CASTLE HALL RESTORED",
    "WEST BANK: SETTLERS TORCH 12 VEHICLES",
    "SUDAN: DRONE STRIKES KILL 5 CHILDREN",
    "NIGERIA: BOAT CAPSIZE KILLS 24",
    "INDONESIA: 36 MISSING IN FACTORY FIRE",
    "OBITUARY: JEWELLER PAOLO BULGARI, 89",
    "UK-EU: POST-BREXIT RESET DEAL AGREED",
    "SEOUL: MINISTER QUITS OVER EXAM AI ROW",
    "POLAND: KYIVSTONER PLOT LINK CONFIRMED",
    "BILA TSERKVA: 1 KILLED IN DRONE STRIKE",
]

MX = 28
RX = 996


# ------------------------------------------------------------------- layout
def draw_masthead(cv):
    cv.fill_rect(0, 12, W, 3, GOLD)
    draw_text_centered(cv, 512, 22, "THE WORLD IN ONE DAY", 6, INK)
    draw_text(cv, MX, 70, "SUNDAY, 22 NOVEMBER 2026", 3, RED)
    draw_text_right(cv, RX, 74, "23 STORIES FROM SUNDAY", 2, NAVY)
    cv.fill_rect(MX, 100, RX - MX, 3, NAVY)


def draw_lead(cv):
    y = 108
    draw_text(cv, MX, y, LEAD["kicker"], 2, RED)
    draw_text(cv, MX, y + 20, LEAD["headline"], 5, INK)
    draw_wrapped(cv, MX, y + 62, LEAD["deck"], 740, 2, INK, leading=16)
    cv.vline(792, y, 132, RULE)
    draw_text_centered(cv, 908, y + 14, LEAD["numeral"], 9, RED)
    draw_text_centered(cv, 908, y + 84, LEAD["num_label"][0], 2, INK)
    draw_text_centered(cv, 908, y + 100, LEAD["num_label"][1], 2, INK)
    cv.fill_rect(MX, 252, RX - MX, 2, NAVY)


def draw_numbers(cv):
    y = 262
    for i, (num, l1, l2) in enumerate(NUMBERS):
        cx = MX + i * 193 + 96
        draw_text_centered(cv, cx, y, num, 4, RED)
        draw_text_centered(cv, cx, y + 34, l1, 2, INK)
        draw_text_centered(cv, cx, y + 50, l2, 2, GREY)
    cv.fill_rect(MX, 340, RX - MX, 2, NAVY)


def draw_grid(cv):
    for idx, (kicker, headline, deck) in enumerate(GRID):
        col = idx % 2
        row = idx // 2
        x = MX + col * 488
        y = 348 + row * 104
        ICONS[idx](cv, x, y + 8)
        tx = x + 68
        draw_text(cv, tx, y + 4, kicker, 2, RED)
        draw_wrapped(cv, tx, y + 22, headline, 412, 3, INK, leading=23)
        draw_wrapped(cv, tx, y + 70, deck, 412, 2, INK, leading=15)
        cv.hline(x, y + 101, 480, SOFT)


def draw_also(cv):
    y = 774
    draw_text(cv, MX, y, "ALSO TODAY", 3, RED)
    draw_text_right(cv, RX, y + 4, "FOURTEEN MORE STORIES FROM SUNDAY", 2, INK)
    cv.fill_rect(MX, y + 24, RX - MX, 2, NAVY)
    for i, item in enumerate(ALSO):
        col = i % 2
        row = i // 2
        x = MX + col * 488
        iy = 808 + row * 24
        cv.fill_rect(x, iy + 3, 8, 8, RED)
        draw_text(cv, x + 16, iy, item, 2, INK)


def draw_footer(cv):
    cv.fill_rect(MX, 976, RX - MX, 1, RULE)
    draw_text_centered(
        cv, 512, 984,
        "SOURCES: BBC - AP - REUTERS - CNN - AL JAZEERA - AFP - LE MONDE - ATP - F1",
        1, GREY)
    draw_text_centered(
        cv, 512, 996,
        "DRAWN BY CODE - NO PHOTOGRAPHS - STORIES AS REPORTED 21-22 NOVEMBER 2026",
        1, GREY)


def build():
    cv = Canvas(W, H, PAPER)
    draw_masthead(cv)
    draw_lead(cv)
    draw_numbers(cv)
    draw_grid(cv)
    draw_also(cv)
    draw_footer(cv)
    return bytes(cv.px)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    write_png(path, W, H, build())


if __name__ == "__main__":
    main()
