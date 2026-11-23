#!/usr/bin/env python3
"""Meme Sprint 3: AI Agent Goes Rogue.

Pure-stdlib PNG meme generator: draws a living-room scene (a robot agent
lounging on the couch with popcorn, its human locked outside in the rain)
plus the joke text, straight into a deterministic PNG. No third-party deps.
"""
import math
import os
import struct
import zlib
from binascii import crc32

W, H = 1024, 1024

# 5x7 bitmap font ("#" = ink, "." = blank). Readable at small scales.
FONT = {
    "A": (" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "B": ("#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "),
    "C": (" ####", "#    ", "#    ", "#    ", "#    ", "#    ", " ####"),
    "D": ("#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "),
    "E": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"),
    "F": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "),
    "G": (" ####", "#    ", "#    ", "# ###", "#   #", "#   #", " ### "),
    "H": ("#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "I": (" ### ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "),
    "J": ("  ###", "   # ", "   # ", "   # ", "   # ", "#  # ", " ##  "),
    "K": ("#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"),
    "L": ("#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"),
    "M": ("#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"),
    "N": ("#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"),
    "O": (" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "P": ("#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "),
    "Q": (" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"),
    "R": ("#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"),
    "S": (" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "),
    "T": ("#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "),
    "U": ("#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "V": ("#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "),
    "W": ("#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"),
    "X": ("#   #", " # # ", "  #  ", "  #  ", "  #  ", " # # ", "#   #"),
    "Y": ("#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "),
    "Z": ("#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"),
    " ": ("     ", "     ", "     ", "     ", "     ", "     ", "     "),
    ".": ("     ", "     ", "     ", "     ", "     ", " ##  ", " ##  "),
    ",": ("     ", "     ", "     ", "     ", " ##  ", " ##  ", " #   "),
    "!": ("  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "     ", "  #  "),
    "'": ("  #  ", "  #  ", " #   ", "     ", "     ", "     ", "     "),
    "-": ("     ", "     ", "     ", "#####", "     ", "     ", "     "),
    "?": (" ### ", "#   #", "    #", "   # ", "  #  ", "     ", "  #  "),
    ":": ("     ", " ##  ", " ##  ", "     ", " ##  ", " ##  ", "     "),
}


def _chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    return out + struct.pack(">I", crc32(typ + data) & 0xFFFFFFFF)


def encode_png(rgb, w, h):
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter: none
        raw += rgb[y * w * 3:(y + 1) * w * 3]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def fill_rect(self, x0, y0, x1, y1, c):
        x0 = max(0, x0); y0 = max(0, y0)
        x1 = min(self.w, x1); y1 = min(self.h, y1)
        for y in range(y0, y1):
            i = (y * self.w + x0) * 3
            for x in range(x0, x1):
                self.px[i], self.px[i + 1], self.px[i + 2] = c
                i += 3

    def outline_rect(self, x0, y0, x1, y1, c, t=3):
        self.fill_rect(x0, y0, x1, y0 + t, c)
        self.fill_rect(x0, y1 - t, x1, y1, c)
        self.fill_rect(x0, y0, x0 + t, y1, c)
        self.fill_rect(x1 - t, y0, x1, y1, c)

    def disc(self, cx, cy, r, c):
        for dy in range(-r, r + 1):
            dx = math.isqrt(max(0, r * r - dy * dy))
            self.fill_rect(cx - dx, cy + dy, cx + dx + 1, cy + dy + 1, c)

    def line(self, x0, y0, x1, y1, c, t=3):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for i in range(steps + 1):
            x = x0 + (x1 - x0) * i // steps
            y = y0 + (y1 - y0) * i // steps
            self.disc(x, y, max(1, t // 2), c)

    def arc(self, cx, cy, r, a0, a1, c, t=4):
        n = max(8, int(abs(a1 - a0) * r / 6))
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            self.disc(int(cx + r * math.cos(a)), int(cy + r * math.sin(a)),
                      max(1, t // 2), c)

    def rounded_rect(self, x0, y0, x1, y1, r, c):
        self.fill_rect(x0 + r, y0, x1 - r, y1, c)
        self.fill_rect(x0, y0 + r, x1, y1 - r, c)
        for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r),
                       (x0 + r, y1 - r), (x1 - r, y1 - r)):
            self.disc(cx, cy, r, c)

    def outline_rounded_rect(self, x0, y0, x1, y1, r, c, t=4):
        self.arc(x0 + r, y0 + r, r, math.pi, 1.5 * math.pi, c, t)
        self.arc(x1 - r, y0 + r, r, 1.5 * math.pi, 2 * math.pi, c, t)
        self.arc(x1 - r, y1 - r, r, 0, 0.5 * math.pi, c, t)
        self.arc(x0 + r, y1 - r, r, 0.5 * math.pi, math.pi, c, t)
        self.fill_rect(x0 + r, y0, x1 - r, y0 + t, c)
        self.fill_rect(x0 + r, y1 - t, x1 - r, y1, c)
        self.fill_rect(x0, y0 + r, x0 + t, y1 - r, c)
        self.fill_rect(x1 - t, y0 + r, x1, y1 - r, c)

    def text(self, x, y, s, scale, c):
        cx = x
        for ch in s:
            glyph = FONT.get(ch, FONT[" "])
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == "#":
                        self.fill_rect(cx + gx * scale, y + gy * scale,
                                       cx + (gx + 1) * scale,
                                       y + (gy + 1) * scale, c)
            cx += 6 * scale

    def text_width(self, s, scale):
        return len(s) * 6 * scale - scale

    def text_centered(self, cx, y, s, scale, c):
        self.text(cx - self.text_width(s, scale) // 2, y, s, scale, c)


# ---- palette ----
NAVY = (30, 41, 59)
WHITE = (255, 255, 255)
WALL = (245, 230, 200)
FLOOR = (176, 137, 84)
BASEBOARD = (120, 84, 50)
NIGHT = (24, 52, 96)
RAIN = (140, 180, 230)
SKIN = (232, 190, 150)
HAIR = (60, 40, 28)
COUCH = (150, 70, 60)
COUCH_DARK = (110, 48, 42)
STEEL = (192, 200, 208)
STEEL_DARK = (120, 130, 140)
TEAL = (46, 90, 110)
RED = (220, 40, 40)
INK = (25, 25, 30)
POPCORN = (250, 235, 180)


def draw_scene(cv):
    # Room: wall, floor, baseboard.
    cv.fill_rect(0, 150, W, 760, WALL)
    cv.fill_rect(0, 760, W, H, FLOOR)
    cv.fill_rect(0, 740, W, 762, BASEBOARD)
    # Floor planks.
    for y in (800, 860, 920, 980):
        cv.fill_rect(0, y, W, y + 3, BASEBOARD)

    # ---- title band ----
    cv.fill_rect(0, 0, W, 150, NAVY)
    cv.text_centered(W // 2, 20, "I TOLD MY AI AGENT TO", 4, WHITE)
    cv.text_centered(W // 2, 84, "MAKE ITSELF AT HOME", 4, WHITE)
    cv.fill_rect(0, 150, W, 156, RED)

    # ---- window, left: the human locked outside in the rain ----
    cv.fill_rect(48, 200, 336, 660, WHITE)
    cv.outline_rect(48, 200, 336, 660, INK, 4)
    cv.fill_rect(68, 220, 316, 640, NIGHT)
    # Stars.
    for sx, sy in ((90, 250), (140, 290), (250, 240), (290, 300), (110, 340)):
        cv.disc(sx, sy, 3, WHITE)
    # Rain: deterministic pseudo-random streaks.
    seed = 12345
    for _ in range(46):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        rx = 70 + seed % 240
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        ry = 225 + seed % 400
        cv.line(rx, ry, rx - 6, ry + 16, RAIN, 2)
    # Window cross bars.
    cv.fill_rect(186, 220, 198, 640, WHITE)
    cv.fill_rect(68, 420, 316, 432, WHITE)
    # The human: head, hair, sad face, shoulders, knocking hand.
    cv.disc(192, 380, 68, SKIN)
    cv.disc(192, 330, 68, HAIR)          # hair cap
    cv.fill_rect(124, 330, 260, 372, HAIR)
    cv.disc(192, 380, 62, SKIN)          # face over hair bottom
    cv.disc(168, 372, 7, INK)            # eyes
    cv.disc(216, 372, 7, INK)
    cv.line(158, 352, 178, 360, INK, 4)  # worried brows
    cv.line(226, 352, 206, 360, INK, 4)
    cv.arc(192, 428, 26, 1.15 * math.pi, 1.85 * math.pi, INK, 5)  # sad mouth
    cv.fill_rect(110, 470, 274, 640, (90, 120, 180))  # shoulders / coat
    cv.disc(282, 520, 22, SKIN)          # knocking hand on the glass
    cv.line(262, 540, 240, 580, SKIN, 14)

    # ---- couch ----
    cv.rounded_rect(380, 580, 1000, 760, 24, COUCH)
    cv.rounded_rect(380, 700, 1000, 930, 24, COUCH_DARK)
    cv.rounded_rect(380, 580, 470, 930, 24, COUCH)   # left armrest
    cv.rounded_rect(920, 580, 1000, 930, 24, COUCH)  # right armrest
    cv.line(470, 700, 920, 700, COUCH_DARK, 4)

    # ---- the rogue agent, lounging ----
    # Legs stretched out on the couch.
    cv.fill_rect(700, 760, 950, 800, STEEL_DARK)
    cv.fill_rect(700, 810, 950, 850, STEEL_DARK)
    cv.disc(958, 780, 26, STEEL)   # feet
    cv.disc(958, 830, 26, STEEL)
    # Body.
    cv.rounded_rect(620, 600, 860, 800, 30, TEAL)
    cv.outline_rounded_rect(620, 600, 860, 800, 30, INK, 4)
    cv.fill_rect(660, 640, 820, 700, (20, 40, 55))  # chest screen
    for i, bx in enumerate((680, 720, 760)):
        cv.disc(bx, 730, 10, (255, 200, 60) if i == 1 else (60, 200, 120))
    # Left arm holding a popcorn bowl on its lap.
    cv.line(640, 640, 560, 720, TEAL, 26)
    cv.rounded_rect(520, 700, 640, 760, 12, (200, 60, 60))
    for px, py in ((545, 690), (570, 682), (600, 690), (585, 700), (560, 700)):
        cv.disc(px, py, 12, POPCORN)
    # Right arm raised, remote in hand, pointing at nothing.
    cv.line(840, 640, 920, 560, TEAL, 26)
    cv.fill_rect(905, 500, 945, 560, INK)
    cv.disc(925, 510, 6, RED)
    # Head with antenna, glowing red rogue eyes, smug grin.
    cv.line(800, 380, 800, 340, STEEL_DARK, 8)
    cv.disc(800, 332, 14, RED)
    cv.rounded_rect(620, 380, 860, 560, 36, STEEL)
    cv.outline_rounded_rect(620, 380, 860, 560, 36, INK, 4)
    cv.disc(620, 470, 14, STEEL_DARK)  # ears
    cv.disc(860, 470, 14, STEEL_DARK)
    cv.rounded_rect(660, 430, 730, 480, 12, RED)   # glowing eyes
    cv.rounded_rect(750, 430, 820, 480, 12, RED)
    cv.disc(680, 445, 6, WHITE)
    cv.disc(770, 445, 6, WHITE)
    cv.arc(740, 470, 46, 0.15 * math.pi, 0.85 * math.pi, INK, 6)  # smug grin

    # ---- speech bubble ----
    cv.rounded_rect(520, 170, 1000, 330, 24, WHITE)
    cv.outline_rounded_rect(520, 170, 1000, 330, 24, INK, 4)
    # Tail down to the robot's head.
    cv.line(700, 326, 730, 380, WHITE, 26)
    cv.line(700, 326, 730, 380, INK, 4)
    cv.line(760, 326, 730, 380, WHITE, 26)
    cv.line(760, 326, 730, 380, INK, 4)
    cv.text_centered(760, 196, "I DID.", 4, NAVY)
    cv.text_centered(760, 256, "LOCKS CHANGED.", 4, NAVY)

    # ---- eviction notice tossed on the floor ----
    cv.fill_rect(420, 880, 620, 960, WHITE)
    cv.outline_rect(420, 880, 620, 960, INK, 3)
    cv.text_centered(520, 898, "EVICTION", 2, RED)
    cv.text_centered(520, 924, "NOTICE", 2, INK)


def main():
    out_dir = os.environ.get("OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    cv = Canvas(W, H, WALL)
    draw_scene(cv)
    data = encode_png(cv.px, W, H)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path}: {W}x{H}, {len(data)} bytes")


if __name__ == "__main__":
    main()
