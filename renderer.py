"""24-bit TrueColor çift tamponlu renderer: ScreenBuffer, DiffWriter, parçacıklar, HUD ve modallar."""
from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

import colors as C
from colors import RGB, cw, mix, shade
from office_map import MAP_H, MAP_W, TH, TW, MapEnv
from simulation import (DAY_LEN, GOAL_FUNDS, MAX_PROJECTS, MAX_WORKERS, UPGRADES,
                        Simulation)
from worker import ROLE_INFO, STATE_INFO, State, Worker

SCREEN_W, SCREEN_H = 125, 38
MAP_OX, MAP_OY = 0, 2
PANEL_X, PANEL_W = MAP_W * TW, SCREEN_W - MAP_W * TW      # 90, 35
BOTTOM_Y = MAP_OY + MAP_H * TH                              # 26


# ====================================================================== tampon
class ScreenBuffer:
    def __init__(self, w: int, h: int, bg: RGB = C.BG) -> None:
        self.w, self.h = w, h
        n = w * h
        self.ch: List[str] = [" "] * n
        self.fg: List[RGB] = [C.TEXT] * n
        self.bg: List[RGB] = [bg] * n

    def clear(self, bg: RGB = C.BG) -> None:
        n = self.w * self.h
        self.ch[:] = [" "] * n
        self.fg[:] = [C.TEXT] * n
        self.bg[:] = [bg] * n

    def bg_at(self, x: int, y: int) -> RGB:
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.bg[y * self.w + x]
        return C.BG

    def _unwide(self, i: int) -> None:
        c = self.ch[i]
        if c == "" and i > 0:
            self.ch[i - 1] = " "
        elif c and cw(c) == 2 and i + 1 < len(self.ch):
            self.ch[i + 1] = " "

    def put(self, x: int, y: int, ch: str, fg: Optional[RGB] = None, bg: Optional[RGB] = None) -> None:
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        wd = cw(ch)
        if wd == 0:
            return
        i = y * self.w + x
        if wd == 2:
            if x + 1 >= self.w:
                return
            self._unwide(i)
            self._unwide(i + 1)
            f = fg or self.fg[i]
            b = bg or self.bg[i]
            self.ch[i], self.ch[i + 1] = ch, ""
            self.fg[i] = self.fg[i + 1] = f
            self.bg[i] = self.bg[i + 1] = b
        else:
            self._unwide(i)
            self.ch[i] = ch
            if fg:
                self.fg[i] = fg
            if bg:
                self.bg[i] = bg

    def text(self, x: int, y: int, s: str, fg: Optional[RGB] = None, bg: Optional[RGB] = None,
             clip: Optional[int] = None) -> int:
        limit = self.w if clip is None else min(clip, self.w)
        for ch in s:
            wd = cw(ch)
            if x + wd > limit:
                break
            self.put(x, y, ch, fg, bg)
            x += wd
        return x

    def fill(self, x: int, y: int, w: int, h: int, bg: RGB, ch: str = " ", fg: Optional[RGB] = None) -> None:
        for yy in range(max(0, y), min(self.h, y + h)):
            for xx in range(max(0, x), min(self.w, x + w)):
                i = yy * self.w + xx
                self._unwide(i)
                self.ch[i] = ch
                self.bg[i] = bg
                if fg:
                    self.fg[i] = fg

    def box(self, x: int, y: int, w: int, h: int, title: str = "", border: RGB = C.PANEL_BORDER,
            bg: RGB = C.PANEL_BG, title_fg: RGB = C.ACCENT) -> None:
        self.fill(x, y, w, h, bg)
        for xx in range(x + 1, x + w - 1):
            self.put(xx, y, "─", border, bg)
            self.put(xx, y + h - 1, "─", border, bg)
        for yy in range(y + 1, y + h - 1):
            self.put(x, yy, "│", border, bg)
            self.put(x + w - 1, yy, "│", border, bg)
        for (cx, cy, c) in ((x, y, "╭"), (x + w - 1, y, "╮"), (x, y + h - 1, "╰"), (x + w - 1, y + h - 1, "╯")):
            self.put(cx, cy, c, border, bg)
        if title:
            self.text(x + 2, y, f" {title} ", title_fg, bg, clip=x + w - 1)

    def dump(self) -> str:
        """Renksiz düz metin (hata ayıklama / test)."""
        rows = []
        for y in range(self.h):
            rows.append("".join(self.ch[y * self.w:(y + 1) * self.w]).rstrip())
        return "\n".join(rows)


class DiffWriter:
    """Yalnızca değişen hücreleri yazan, titreşimsiz farksal yazıcı."""

    def __init__(self, out=None) -> None:
        self.out = out or sys.stdout
        self.prev: Optional[Tuple[List[str], List[RGB], List[RGB]]] = None
        self.size = (0, 0)

    def invalidate(self) -> None:
        self.prev = None

    def render_diff(self, buf: ScreenBuffer) -> str:
        w, h = buf.w, buf.h
        full = self.prev is None or self.size != (w, h)
        pch, pfg, pbg = self.prev if self.prev is not None else ([], [], [])
        parts: List[str] = []
        cur_fg = cur_bg = None
        for y in range(h):
            row = y * w
            x = 0
            cursor = -1
            while x < w:
                i = row + x
                c = buf.ch[i]
                if c == "":
                    x += 1
                    continue
                if not full and c == pch[i] and buf.fg[i] == pfg[i] and buf.bg[i] == pbg[i]:
                    x += 1
                    continue
                if cursor != x:
                    parts.append(f"\033[{y + 1};{x + 1}H")
                f, b = buf.fg[i], buf.bg[i]
                if f != cur_fg:
                    parts.append(C.fg(f))
                    cur_fg = f
                if b != cur_bg:
                    parts.append(C.bg(b))
                    cur_bg = b
                parts.append(c)
                step = cw(c) or 1
                x += step
                cursor = x
        self.prev = (buf.ch[:], buf.fg[:], buf.bg[:])
        self.size = (w, h)
        if not parts:
            return ""
        return C.SYNC_ON + "".join(parts) + C.RESET + C.SYNC_OFF

    def flush(self, buf: ScreenBuffer) -> int:
        s = self.render_diff(buf)
        if s:
            self.out.write(s)
            self.out.flush()
        return len(s)


# ====================================================================== parçacıklar
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "ch", "color", "life", "max", "sway")

    def __init__(self, x, y, ch, color, life, vx=0.0, vy=0.0, sway=0.0) -> None:
        self.x, self.y, self.ch, self.color = x, y, ch, color
        self.life = self.max = life
        self.vx, self.vy, self.sway = vx, vy, sway


class Particles:
    CAP = 450

    def __init__(self) -> None:
        self.items: List[Particle] = []

    def spawn(self, *a, **k) -> None:
        if len(self.items) < self.CAP:
            self.items.append(Particle(*a, **k))

    def update(self, dt: float) -> None:
        keep = []
        for p in self.items:
            p.life -= dt
            if p.life <= 0:
                continue
            p.x += p.vx * dt + math.sin(p.life * 6 + p.y) * p.sway * dt
            p.y += p.vy * dt
            keep.append(p)
        self.items = keep

    def draw(self, buf: ScreenBuffer) -> None:
        for p in self.items:
            x, y = int(round(p.x)), int(round(p.y))
            if not (0 <= x < PANEL_X and MAP_OY - 1 <= y < BOTTOM_Y):
                continue
            k = min(1.0, (p.life / p.max) * 1.8)
            col = mix(buf.bg_at(x, y), p.color, k)
            buf.text(x, y, p.ch, col, None, clip=PANEL_X)


# ====================================================================== UI durumu
@dataclass
class UIState:
    mode: str = "normal"       # normal|hire|project|bonus|upgrade|fire
    cursor: int = 0
    selected: int = 0
    paused: bool = False
    speed: int = 1
    flash_text: str = ""
    flash_color: RGB = C.TEXT
    flash_t: float = 0.0

    def flash(self, text: str, color: RGB = C.TEXT, secs: float = 3.0) -> None:
        self.flash_text, self.flash_color, self.flash_t = text, color, secs


def money(v: int) -> str:
    return f"-${-v:,}" if v < 0 else f"${v:,}"


def meter(v: float, vmax: float, width: int) -> Tuple[str, str, RGB]:
    n = int(round(max(0.0, min(1.0, v / vmax)) * width))
    col = C.gradient([(0.0, C.BAD), (0.5, C.WARN), (1.0, C.GOOD)], v / vmax)
    return "█" * n, "░" * (width - n), col


# ====================================================================== renderer
class Renderer:
    def __init__(self, w: int = SCREEN_W, h: int = SCREEN_H) -> None:
        self.buf = ScreenBuffer(w, h)
        self.parts = Particles()
        self.rnd = random.Random(7)
        self.t = 0.0

    # ------------------------------------------------------------ yardımcılar
    def bar(self, x: int, y: int, v: float, vmax: float, width: int, bg: RGB = C.PANEL_BG) -> None:
        on, off, col = meter(v, vmax, width)
        self.buf.text(x, y, on, col, bg)
        self.buf.text(x + len(on), y, off, shade(col, 0.28), bg)

    def _hp(self, wx: float, wy: float) -> Tuple[int, int]:
        return MAP_OX + int(round(wx * TW)), MAP_OY + int(round(wy * TH))

    # ------------------------------------------------------------ efekt üretimi
    def _spawn_effects(self, sim: Simulation, dt: float) -> None:
        r, P = self.rnd.random, self.parts
        for w in sim.workers:
            hx, hy = self._hp(w.px, w.py)
            if w.producing:
                if r() < 6 * dt:
                    dx, dy = self._hp(w.seat[0], w.seat[1] - 1)
                    P.spawn(dx + 1 + self.rnd.choice((-1, 0, 1)), dy - 1, "·", (120, 255, 220), 0.9, vy=-3.5, sway=1.5)
                if w.state is State.STRESSED and r() < 2.5 * dt:
                    P.spawn(hx + 2, hy, "°", (110, 180, 255), 0.8, vy=2.5)
            elif w.state is State.SLEEPING and r() < 1.4 * dt:
                P.spawn(hx + 2, hy - 1, self.rnd.choice("zZ"), (160, 175, 255), 1.6, vx=1.2, vy=-1.4, sway=1.0)
            elif w.state is State.PANIC and r() < 3 * dt:
                P.spawn(hx + 1, hy - 1, "!", C.BAD, 0.7, vy=-2)
            elif w.state is State.CELEBRATING and r() < 9 * dt:
                ch = self.rnd.choice(["✨", "*", "✦", "·"])
                P.spawn(hx + 1 + self.rnd.uniform(-3, 3), hy - 1, ch, C.hsv(self.rnd.uniform(0, 360), 0.6, 1.0),
                        1.3, vx=self.rnd.uniform(-3, 3), vy=-self.rnd.uniform(1, 4))
            if (w.cup_t > 0 or (w.state is State.COFFEE_RUN and w.phase == "act")) and r() < 3 * dt:
                P.spawn(hx + 2, hy - 1, "~", (230, 230, 240), 0.9, vy=-2.2, sway=2.0)
        cx, cy = self._hp(3, 1)
        if sim.coffee_broken > 0:
            if r() < 5 * dt:
                P.spawn(cx + 1, cy - 1, self.rnd.choice(["▒", "°", "░"]), (150, 150, 160), 1.3, vy=-2.5, sway=2.5)
        elif r() < 1.5 * dt:
            P.spawn(cx + 1, cy - 1, "~", (235, 235, 245), 1.2, vy=-1.8, sway=2.0)
        if sim.alert is not None:
            for sx in (22, 23, 25, 26, 28):
                if r() < 2.2 * dt:
                    fx, fy = self._hp(sx, 1)
                    P.spawn(fx, fy - 1, "🔥", C.BAD, 1.3, vx=self.rnd.uniform(-1, 1), vy=-2.2)
                if r() < 3 * dt:
                    fx, fy = self._hp(sx, 1)
                    P.spawn(fx + 1, fy - 1, "▒", (90, 90, 100), 1.4, vy=-2.6, sway=2)
        for kind, data in sim.fx:
            if kind == "celebrate":
                for _ in range(26):
                    P.spawn(self.rnd.uniform(2, PANEL_X - 3), self.rnd.uniform(MAP_OY + 4, BOTTOM_Y - 4),
                            self.rnd.choice(["✨", "*", "✦"]), C.hsv(self.rnd.uniform(0, 360), 0.6, 1.0),
                            self.rnd.uniform(1.0, 2.2), vy=-self.rnd.uniform(1, 3), vx=self.rnd.uniform(-2, 2))
            elif kind == "donut":
                for _ in range(14):
                    P.spawn(self.rnd.uniform(2, PANEL_X - 4), MAP_OY - 1 - self.rnd.uniform(0, 6), "🍩",
                            (230, 160, 90), 3.2, vy=self.rnd.uniform(6, 9), sway=1)
            elif kind == "bulb":
                for _ in range(10):
                    P.spawn(self.rnd.uniform(4, PANEL_X - 6), self.rnd.uniform(MAP_OY + 8, BOTTOM_Y - 3), "💡",
                            C.GOLD, 2.2, vy=-self.rnd.uniform(2, 4))
            elif kind == "money":
                col = C.GOOD if str(data).startswith("+") else C.BAD
                P.spawn(30, MAP_OY + 1, str(data), col, 2.2, vy=-1.5)
            elif kind == "snacks":
                for _ in range(8):
                    P.spawn(self.rnd.uniform(4, 40), MAP_OY + 5, self.rnd.choice(["🍩", "☕"]), C.WARN, 2.0,
                            vy=-self.rnd.uniform(1, 3))
        sim.fx.clear()

    # ------------------------------------------------------------ çalışan çizimi
    def _draw_worker(self, w: Worker, selected: bool) -> None:
        b, t = self.buf, self.t
        x, y = self._hp(w.px, w.py)
        info = ROLE_INFO[w.role]
        shirt = info.color
        skin = w.skin
        cele = w.state is State.CELEBRATING
        if cele and int(t * 6 + w.wid) % 2 == 0:
            y -= 1
        if w.state is State.STRESSED:
            skin = mix(skin, (230, 80, 70), 0.4)
        if w.state is State.PANIC and int(t * 8) % 2 == 0:
            shirt = mix(shirt, (255, 255, 255), 0.5)
        if w.state is State.SLEEPING:
            shirt = shade(shirt, 0.65)
            b.put(x + 1, y, "▄", skin, None)
        else:
            b.put(x + 1, y, "▀", w.hair, skin)
        if cele:
            b.put(x, y, "\\", C.GOLD, None)
            b.put(x + 2, y, "/", C.GOLD, None)
        phase = int(t * 8 + w.wid) % 2
        if w.moving:
            row = ("▟▓▙", "▐█▌")[phase]
        elif w.producing:
            row = ("▟█▗", "▖█▙")[phase]
        else:
            row = "▟█▙"
        for i, chr_ in enumerate(row):
            b.put(x + i, y + 1, chr_, shirt, None)
        if selected:
            b.put(x + 1, y - 1, "▼", C.GOLD, None)
        if w.bubble_t > 0 and w.bubble:
            txt = f" {w.bubble} "
            bx = max(0, min(PANEL_X - len(txt), x + 1 - len(txt) // 2))
            b.text(bx, y - 1, txt, (30, 32, 44), (245, 245, 250), clip=PANEL_X)

    # ------------------------------------------------------------ üst çubuk
    def _top_bar(self, sim: Simulation, ui: UIState) -> None:
        b = self.buf
        b.fill(0, 0, SCREEN_W, 2, (18, 20, 32))
        title = " ▓▒░ OFFICE MANAGER TYCOON "
        for i, ch in enumerate(title):
            b.put(1 + i, 0, ch, C.hsv(190 + i * 5, 0.7, 1.0), None)
        x = 30
        fcol = C.GOOD if sim.funds > 2000 else C.WARN if sim.funds > 0 else C.BAD
        x = b.text(x, 0, " BÜTÇE ", C.DIM, None)
        x = b.text(x, 0, money(sim.funds), fcol, None)
        x = b.text(x + 2, 0, f"Gün {sim.day}", C.TEXT, None)
        x = b.text(x + 2, 0, sim.clock, C.ACCENT, None)
        x += 1
        b.text(x, 0, "[", C.DIM)
        n = int(sim.day_frac * 14)
        b.text(x + 1, 0, "█" * n, C.ACCENT)
        b.text(x + 1 + n, 0, "░" * (14 - n), (50, 60, 80))
        b.text(x + 15, 0, "]", C.DIM)
        x += 18
        if ui.paused or ui.mode != "normal":
            x = b.text(x, 0, " II DURAKLATILDI ", C.BLACK, C.WARN)
        else:
            x = b.text(x, 0, f" {'>' * ui.speed} {ui.speed}x ", C.BLACK, C.ACCENT)
        if sim.crunch:
            hot = (255, 60, 40) if int(self.t * 4) % 2 == 0 else (200, 30, 30)
            b.text(x + 1, 0, " CRUNCH ", C.WHITE, hot)
        # satır 1
        if sim.alert is not None:
            a = sim.alert
            flash = (110, 20, 20) if int(self.t * 4) % 2 == 0 else (70, 12, 12)
            b.fill(0, 1, SCREEN_W, 1, flash)
            pct = int(100 * a.progress / a.need)
            b.text(1, 1, f"🔥 ALARM: {a.title}  müdahale %{min(100, pct)}  kalan {int(a.timer)} sn", C.WHITE, flash)
        elif sim.banner is not None:
            col = sim.banner.color
            b.fill(0, 1, SCREEN_W, 1, shade(col, 0.28))
            b.text(1, 1, sim.banner.text, C.WHITE, shade(col, 0.28))
        elif ui.flash_t > 0:
            b.text(1, 1, ui.flash_text, ui.flash_color, None)
        else:
            msg = (f"Günlük gider ~{money(sim.daily_burn())}  |  Bugünkü gelir {money(sim.income_today)}  |  "
                   f"Ort. moral %{sim.avg_morale():.0f}  |  Teslim: {sim.delivered}  |  Hedef: {money(GOAL_FUNDS)}")
            b.text(1, 1, msg, C.DIM)

    # ------------------------------------------------------------ yan paneller
    def _projects_panel(self, sim: Simulation) -> None:
        b = self.buf
        b.box(PANEL_X, MAP_OY, PANEL_W, 11, f"SPRINTLER {len(sim.projects)}/{MAX_PROJECTS}")
        if not sim.projects:
            b.text(PANEL_X + 2, MAP_OY + 2, "Aktif sprint yok!", C.WARN)
            b.text(PANEL_X + 2, MAP_OY + 3, "[P] ile yeni proje başlat", C.DIM)
        for i, p in enumerate(sim.projects[:MAX_PROJECTS]):
            y = MAP_OY + 1 + i * 3
            left = p.deadline_day - sim.day
            dl = f"{left}g" if left >= 0 else "GEÇ!"
            b.text(PANEL_X + 2, y, p.name, C.WHITE, clip=PANEL_X + PANEL_W - 8)
            b.text(PANEL_X + PANEL_W - 7, y, f"son {dl}", C.BAD if left < 1 else C.DIM)
            n = int(p.progress * 18)
            b.text(PANEL_X + 2, y + 1, "[", C.DIM)
            b.text(PANEL_X + 3, y + 1, "█" * n, C.GOOD if p.progress > .66 else C.ACCENT)
            b.text(PANEL_X + 3 + n, y + 1, "░" * (18 - n), (50, 60, 80))
            b.text(PANEL_X + 21, y + 1, f"] %{int(p.progress * 100)}", C.DIM)
            qc = C.GOOD if p.quality >= 70 else C.WARN if p.quality >= 50 else C.BAD
            b.text(PANEL_X + 2, y + 2, f"Kalite {p.quality:3.0f}", qc)
            b.text(PANEL_X + 14, y + 2, f"Bug {int(p.bugs)}", C.BAD if p.bugs >= 5 else C.TEXT)
            b.text(PANEL_X + 23, y + 2, money(p.reward), C.GOLD)

    def _roster_panel(self, sim: Simulation, ui: UIState) -> None:
        b = self.buf
        y0 = MAP_OY + 11
        b.box(PANEL_X, y0, PANEL_W, BOTTOM_Y - y0, f"EKİP {len(sim.workers)}/{MAX_WORKERS}  moral · enerji")
        for i, w in enumerate(sim.workers[:MAX_WORKERS]):
            y = y0 + 1 + i
            sel = i == ui.selected
            bgc = (44, 52, 80) if sel else C.PANEL_BG
            b.fill(PANEL_X + 1, y, PANEL_W - 2, 1, bgc)
            info = ROLE_INFO[w.role]
            b.text(PANEL_X + 1, y, "▸" if sel else " ", C.GOLD, bgc)
            b.text(PANEL_X + 2, y, w.name, C.WHITE if sel else C.TEXT, bgc, clip=PANEL_X + 13)
            b.text(PANEL_X + 14, y, info.short, info.color, bgc)
            self.bar(PANEL_X + 17, y, w.morale, 100, 5, bgc)
            self.bar(PANEL_X + 23, y, w.energy, 100, 5, bgc)
            code, col, _ = STATE_INFO[w.state]
            b.text(PANEL_X + 29, y, code, col, bgc)

    def _card(self, sim: Simulation, ui: UIState) -> None:
        b = self.buf
        b.box(0, BOTTOM_Y, 40, SCREEN_H - BOTTOM_Y, "SEÇİLİ ÇALIŞAN")
        if not sim.workers:
            return
        w = sim.workers[min(ui.selected, len(sim.workers) - 1)]
        info = ROLE_INFO[w.role]
        b.text(2, BOTTOM_Y + 1, w.name, C.WHITE, clip=38)
        b.text(2, BOTTOM_Y + 2, info.title, info.color)
        b.text(2, BOTTOM_Y + 4, "Yetenek", C.DIM)
        self.bar(11, BOTTOM_Y + 4, w.skill, 10, 12)
        b.text(24, BOTTOM_Y + 4, f"{w.skill}/10", C.TEXT)
        b.text(2, BOTTOM_Y + 5, "Moral  ", C.DIM)
        self.bar(11, BOTTOM_Y + 5, w.morale, 100, 12)
        b.text(24, BOTTOM_Y + 5, f"{w.morale:3.0f}", C.TEXT)
        b.text(2, BOTTOM_Y + 6, "Enerji ", C.DIM)
        self.bar(11, BOTTOM_Y + 6, w.energy, 100, 12)
        b.text(24, BOTTOM_Y + 6, f"{w.energy:3.0f}", C.TEXT)
        b.text(2, BOTTOM_Y + 8, "Maaş   ", C.DIM)
        b.text(11, BOTTOM_Y + 8, f"{money(w.salary)}/gün", C.GOLD)
        b.text(2, BOTTOM_Y + 9, "Verim  ", C.DIM)
        b.text(11, BOTTOM_Y + 9, f"{w.rate(sim):.2f} puan/sn", C.TEXT)
        b.text(2, BOTTOM_Y + 10, w.activity(), STATE_INFO[w.state][1], clip=39)

    @staticmethod
    def _wrap(text: str, width: int) -> List[str]:
        lines, cur, used = [], "", 0
        for ch in text:
            wd = cw(ch)
            if used + wd > width:
                lines.append(cur)
                cur, used = "  ", 2
            cur += ch
            used += wd
        lines.append(cur)
        return lines

    def _log(self, sim: Simulation) -> None:
        b = self.buf
        b.box(40, BOTTOM_Y, 50, SCREEN_H - BOTTOM_Y, "OLAY GÜNLÜĞÜ")
        rows = SCREEN_H - BOTTOM_Y - 2
        out: List[Tuple[str, str, RGB]] = []
        for clock, text, col in list(sim.log)[-rows:]:
            for j, part in enumerate(self._wrap(text, 40)):
                out.append((clock if j == 0 else "", part, col))
        for i, (clock, text, col) in enumerate(out[-rows:]):
            y = BOTTOM_Y + 1 + i
            b.text(42, y, clock, C.DIM)
            b.text(48, y, text, col, clip=89)

    def _help(self) -> None:
        b = self.buf
        b.box(PANEL_X, BOTTOM_Y, PANEL_W, SCREEN_H - BOTTOM_Y, "KOMUTLAR")
        keys = [("H", "İşe Al"), ("F", "Kov"), ("P", "Yeni Sprint"), ("B", "Prim Dağıt"),
                ("C", "Kahve/Snack"), ("U", "Yükselt"),
                ("M", "Toplantı"), ("K", "Crunch"), ("Spc", "Duraklat"), ("1-3", "Hız 1/2/4x"),
                ("←→", "Seç"), ("Q", "Çıkış")]
        for i, (k, d) in enumerate(keys):
            col, row = divmod(i, 6)
            x = PANEL_X + 2 + col * 16
            y = BOTTOM_Y + 1 + row
            b.text(x, y, f"[{k}]", C.GOLD)
            b.text(x + len(k) + 3, y, d, C.TEXT, clip=PANEL_X + PANEL_W - 1)
        b.text(PANEL_X + 2, BOTTOM_Y + 8, "Menüler açıkken sim durur.", C.DIM)

    # ------------------------------------------------------------ modallar
    def _modal(self, title: str, lines: List[Tuple[str, RGB]], footer: str, w: int = 78, cursor: int = -1) -> None:
        b = self.buf
        h = len(lines) + 4
        x = (PANEL_X - w) // 2
        y = MAP_OY + max(1, (MAP_H * TH - h) // 2)
        b.box(x, y, w, h, title, C.ACCENT, (16, 20, 34), C.GOLD)
        for i, (s, col) in enumerate(lines):
            bgc = (46, 60, 98) if i == cursor else (16, 20, 34)
            b.fill(x + 1, y + 1 + i, w - 2, 1, bgc)
            b.text(x + 2, y + 1 + i, ("▸ " if i == cursor else "  ") + s, col if i != cursor else C.WHITE, bgc, clip=x + w - 1)
        b.text(x + 2, y + h - 2, footer, C.DIM, (16, 20, 34), clip=x + w - 1)

    def _modals(self, sim: Simulation, ui: UIState) -> None:
        m = ui.mode
        if m == "hire":
            lines = []
            for c in sim.candidates:
                rt = ROLE_INFO[c.role]
                lines.append((f"{c.name:<18}{rt.title:<22} Yet {c.skill}/10  Maaş {money(c.salary):>5}/gün  Ücret {money(c.fee):>6}", rt.color))
            if not lines:
                lines = [("Bugün aday yok. Yarın yeni başvurular gelir.", C.DIM)]
            self._modal("İŞE ALIM — Başvuran Adaylar", lines, "↑↓ seç  Enter/1-4 işe al  R yenile (-$150)  Esc geri", cursor=ui.cursor)
        elif m == "project":
            lines = []
            for p in sim.offers:
                top = sorted(p.needs.items(), key=lambda kv: -kv[1])[:3]
                need = " ".join(f"{ROLE_INFO[r].short}:{int(v)}" for r, v in top)
                lines.append((f"{p.name:<22} {int(p.size):>4} puan  {money(p.reward):>7}  {p.deadline_day - sim.day:>2} gün  {need}", C.TEXT))
            self._modal("YENİ SPRINT — Müşteri Teklifleri", lines, "↑↓ seç  Enter/1-3 başlat  Esc geri", cursor=ui.cursor)
        elif m == "bonus":
            n = len(sim.workers)
            who = sim.workers[min(ui.selected, n - 1)].name if n else "-"
            lines = [(f"Seçili çalışana: {who}   (-$300, +35 moral)", C.TEXT),
                     (f"Tüm ekibe   (-{money(150 * n)}, +20 moral)", C.TEXT)]
            self._modal("PRİM DAĞIT", lines, "↑↓ seç  Enter/1-2 onayla  Esc geri", 60, ui.cursor)
        elif m == "upgrade":
            lines = []
            for key, (name, cost, desc) in UPGRADES.items():
                own = key in sim.upgrades
                lines.append((f"{'[x]' if own else '[ ]'} {name:<24} {money(cost):>7}   {desc}", C.GOOD if own else C.TEXT))
            self._modal("OFİS YÜKSELTMELERİ", lines, "↑↓ seç  Enter/1-5 satın al  Esc geri", 76, ui.cursor)
        elif m == "fire":
            w = sim.workers[min(ui.selected, len(sim.workers) - 1)]
            lines = [(f"{w.name} ({ROLE_INFO[w.role].title}) kovulsun mu?", C.WHITE),
                     (f"Tazminat: {money(w.salary * 3)}  ·  Ekibin morali -5 düşer.", C.WARN)]
            self._modal("İŞTEN ÇIKARMA", lines, "[Y] Evet, kov    [N/Esc] Vazgeç", 62)

    def _game_over(self, sim: Simulation) -> None:
        b = self.buf
        b.box(30, 14, 60, 9, "OYUN BİTTİ", C.BAD, (30, 10, 14), C.BAD)
        b.text(34, 16, sim.game_over, C.WHITE, (30, 10, 14))
        b.text(34, 18, f"Hayatta kalınan gün: {sim.day}   Teslim edilen sprint: {sim.delivered}", C.TEXT, (30, 10, 14))
        b.text(34, 20, "[R] Yeniden başla     [Q] Çıkış", C.GOLD, (30, 10, 14))

    # ------------------------------------------------------------ ana çizim
    def render(self, sim: Simulation, ui: UIState, dt: float) -> ScreenBuffer:
        self.t += dt
        b = self.buf
        b.clear(C.BG)
        env = MapEnv(t=self.t, day_frac=sim.day_frac, upgrades=sim.upgrades,
                     alert=sim.alert is not None, coffee_broken=sim.coffee_broken > 0,
                     active_desks={sim.office.desk_of(w.seat) for w in sim.workers if w.producing})
        sim.office.draw(b, MAP_OX, MAP_OY, env)
        sel_w = sim.workers[ui.selected] if 0 <= ui.selected < len(sim.workers) else None
        for w in sorted(sim.workers, key=lambda k: k.py):
            self._draw_worker(w, w is sel_w)
        self._spawn_effects(sim, dt)
        self.parts.update(dt)
        self.parts.draw(b)
        self._top_bar(sim, ui)
        self._projects_panel(sim)
        self._roster_panel(sim, ui)
        self._card(sim, ui)
        self._log(sim)
        self._help()
        if ui.mode != "normal":
            self._modals(sim, ui)
        if sim.game_over:
            self._game_over(sim)
        return b
