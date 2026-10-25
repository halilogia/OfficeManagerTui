"""24-bit TrueColor ANSI yardımcıları, ofis paleti ve Windows VT kurulumu."""
from __future__ import annotations

import math
import sys
import unicodedata
from collections.abc import Sequence
from typing import Tuple

RGB = Tuple[int, int, int]

ESC = "\033"
RESET = f"{ESC}[0m"
HIDE_CURSOR = f"{ESC}[?25l"
SHOW_CURSOR = f"{ESC}[?25h"
ALT_ON = f"{ESC}[?1049h"
ALT_OFF = f"{ESC}[?1049l"
CLEAR = f"{ESC}[2J"
HOME = f"{ESC}[H"
SYNC_ON = f"{ESC}[?2026h"
SYNC_OFF = f"{ESC}[?2026l"


def fg(c: RGB) -> str:
    return f"\033[38;2;{c[0]};{c[1]};{c[2]}m"


def bg(c: RGB) -> str:
    return f"\033[48;2;{c[0]};{c[1]};{c[2]}m"


def paint(text: str, fgc: RGB | None = None, bgc: RGB | None = None, bold: bool = False) -> str:
    pre = ("\033[1m" if bold else "") + (fg(fgc) if fgc else "") + (bg(bgc) if bgc else "")
    return f"{pre}{text}{RESET}"


def clamp8(v: float) -> int:
    return 0 if v < 0 else 255 if v > 255 else int(v)


def mix(a: RGB, b: RGB, t: float) -> RGB:
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return (clamp8(a[0] + (b[0] - a[0]) * t),
            clamp8(a[1] + (b[1] - a[1]) * t),
            clamp8(a[2] + (b[2] - a[2]) * t))


def shade(c: RGB, f: float) -> RGB:
    return (clamp8(c[0] * f), clamp8(c[1] * f), clamp8(c[2] * f))


def hsv(h: float, s: float, v: float) -> RGB:
    h = (h % 360) / 60.0
    i = int(h)
    f = h - i
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i % 6]
    return (clamp8(r * 255), clamp8(g * 255), clamp8(b * 255))


def gradient(stops: Sequence[Tuple[float, RGB]], t: float) -> RGB:
    if t <= stops[0][0]:
        return stops[0][1]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            return mix(c0, c1, (t - t0) / (t1 - t0) if t1 > t0 else 0.0)
    return stops[-1][1]


def pulse(t: float, speed: float = 1.0) -> float:
    """0..1 arası yumuşak nabız."""
    return 0.5 + 0.5 * math.sin(t * speed * math.tau)


_WIDTH: dict = {}


def cw(ch: str) -> int:
    """Karakterin terminaldeki hücre genişliği (emoji = 2)."""
    if not ch:
        return 0
    w = _WIDTH.get(ch)
    if w is None:
        if unicodedata.combining(ch):
            w = 0
        else:
            w = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        _WIDTH[ch] = w
    return w


def text_width(s: str) -> int:
    return sum(cw(c) for c in s)


# ---------------------------------------------------------------- palet
WHITE: RGB = (236, 238, 245)
BLACK: RGB = (8, 9, 14)
BG: RGB = (14, 16, 24)
PANEL_BG: RGB = (22, 25, 36)
PANEL_BORDER: RGB = (70, 80, 110)
TEXT: RGB = (205, 210, 225)
DIM: RGB = (110, 118, 140)
ACCENT: RGB = (0, 200, 255)
GOOD: RGB = (80, 220, 130)
WARN: RGB = (255, 200, 70)
BAD: RGB = (255, 90, 80)
GOLD: RGB = (255, 215, 90)

FLOOR_A: RGB = (60, 65, 78)
FLOOR_B: RGB = (66, 71, 85)
GROUT: RGB = (46, 50, 61)
CARPET: RGB = (112, 30, 44)
CARPET_HI: RGB = (134, 42, 58)
RUG: RGB = (28, 92, 100)
RUG_HI: RGB = (38, 112, 120)
SERVER_FLOOR: RGB = (28, 34, 46)
WALL_TOP: RGB = (128, 136, 156)
WALL_FACE: RGB = (74, 80, 98)
WOOD: RGB = (150, 100, 56)
WOOD_HI: RGB = (176, 122, 70)
WOOD_DARK: RGB = (112, 72, 42)
STEEL: RGB = (150, 160, 176)
STEEL_DARK: RGB = (52, 58, 70)
MONITOR_ON: RGB = (0, 210, 255)
MONITOR_OFF: RGB = (28, 34, 44)
LEAF: RGB = (52, 168, 84)
LEAF_HI: RGB = (90, 205, 110)
POT: RGB = (182, 92, 62)
COUCH: RGB = (96, 78, 156)
COUCH_HI: RGB = (122, 104, 186)
COFFEE_COL: RGB = (196, 88, 48)
WATER_COL: RGB = (120, 200, 255)


def enable_vt() -> bool:
    """Windows konsolunda VT100 + UTF-8 modunu açar."""
    reconf = getattr(sys.stdout, "reconfigure", None)
    if reconf is not None:
        try:
            reconf(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        k32 = ctypes.windll.kernel32
        k32.SetConsoleOutputCP(65001)
        k32.SetConsoleCP(65001)
        h = k32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if not k32.GetConsoleMode(h, ctypes.byref(mode)):
            return False
        # ENABLE_PROCESSED_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return bool(k32.SetConsoleMode(h, mode.value | 0x0001 | 0x0004))
    except Exception:
        return False
