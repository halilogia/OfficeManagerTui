"""Ofis kat planı: 2B karo matrisi, eşyalar, pathfinding ve karo çizimi.

Her karo ekranda 3x2 karakterdir (TW x TH). Harita 30x12 karo = 90x24 karakter.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Set, Tuple

import colors as C
from colors import RGB, mix, shade

TW, TH = 3, 2
MAP_W, MAP_H = 30, 12
Pos = Tuple[int, int]


class Tile(IntEnum):
    FLOOR = 0
    WALL = 1
    CARPET = 2
    DESK = 3
    SEAT = 4
    COFFEE = 5
    WATER = 6
    PLANT = 7
    SERVER = 8
    TABLE = 9
    COUCH = 10
    ARCADE = 11
    BAR = 12
    WINDOW = 13
    RUG = 14
    SFLOOR = 15


WALKABLE = {Tile.FLOOR, Tile.CARPET, Tile.SEAT, Tile.RUG, Tile.SFLOOR}

SKY_STOPS = [(0.0, (250, 196, 140)), (0.3, (130, 196, 255)), (0.7, (150, 204, 255)),
             (0.9, (255, 140, 90)), (1.0, (66, 58, 112))]


@dataclass
class MapEnv:
    """Çizim anında haritanın bilmesi gereken dinamik durum."""
    t: float = 0.0
    day_frac: float = 0.0
    active_desks: Set[Pos] = field(default_factory=set)
    upgrades: Set[str] = field(default_factory=set)
    alert: bool = False
    coffee_broken: bool = False


Cell = Tuple[str, RGB, RGB]


class OfficeMap:
    def __init__(self) -> None:
        self.w, self.h = MAP_W, MAP_H
        self.grid: List[List[Tile]] = [[Tile.FLOOR] * MAP_W for _ in range(MAP_H)]
        self.seats: List[Pos] = []
        self.spots: Dict[str, List[Pos]] = {}
        self.entrance: Pos = (1, 8)
        self.optional = {"arcade": ((27, 9), Tile.ARCADE), "coffee_bar": ((4, 1), Tile.BAR)}
        self.window_cols = (2, 5, 8, 12, 15, 18, 23, 26)
        self._build()

    # ------------------------------------------------------------ yerleşim
    def _set(self, x: int, y: int, t: Tile) -> None:
        self.grid[y][x] = t

    def _rect(self, x0: int, y0: int, x1: int, y1: int, t: Tile) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self._set(x, y, t)

    def _build(self) -> None:
        self._rect(0, 0, MAP_W - 1, 0, Tile.WALL)
        self._rect(0, MAP_H - 1, MAP_W - 1, MAP_H - 1, Tile.WALL)
        self._rect(0, 0, 0, MAP_H - 1, Tile.WALL)
        self._rect(MAP_W - 1, 0, MAP_W - 1, MAP_H - 1, Tile.WALL)
        for x in self.window_cols:
            self._set(x, 0, Tile.WINDOW)
        # sunucu odası
        self._rect(20, 0, 20, 5, Tile.WALL)
        self._rect(20, 5, MAP_W - 1, 5, Tile.WALL)
        self._rect(21, 1, 28, 4, Tile.SFLOOR)
        self._set(20, 4, Tile.FLOOR)
        for x in (22, 23, 25, 26, 28):
            self._set(x, 1, Tile.SERVER)
        self.spots["server"] = [(22, 3), (23, 3), (24, 3), (25, 3), (26, 3), (27, 3), (24, 2), (27, 2)]
        # mutfak
        self._set(3, 1, Tile.COFFEE)
        self._set(6, 1, Tile.WATER)
        for p in ((1, 1), (9, 1), (19, 1), (1, 10), (19, 10), (28, 7), (28, 10), (19, 5)):
            self._set(p[0], p[1], Tile.PLANT)
        self.spots["coffee"] = [(3, 2), (4, 2), (2, 2)]
        self.spots["cooler"] = [(5, 2), (6, 2), (7, 2)]
        # toplantı
        self._rect(10, 1, 18, 4, Tile.CARPET)
        self._rect(12, 2, 16, 3, Tile.TABLE)
        meet = [(11, 2), (11, 3), (17, 2), (17, 3)]
        meet += [(x, 1) for x in range(12, 17)] + [(x, 4) for x in range(12, 17)]
        self.spots["meeting"] = meet
        # masalar + koltuklar
        for cx in (2, 5, 8, 11, 14, 17):
            for desk_y in (6, 9):
                self._set(cx, desk_y, Tile.DESK)
                self._set(cx, desk_y + 1, Tile.SEAT)
                self.seats.append((cx, desk_y + 1))
        # dinlenme alanı
        self._rect(22, 7, 27, 10, Tile.RUG)
        for x in (23, 24, 25):
            self._set(x, 8, Tile.COUCH)
        self.spots["lounge"] = [(23, 9), (24, 9), (25, 9), (22, 8), (26, 8)]

    def apply_upgrade(self, key: str) -> None:
        if key in self.optional:
            (x, y), tile = self.optional[key]
            self._set(x, y, tile)

    # ------------------------------------------------------------ sorgular
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h

    def walkable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.grid[y][x] in WALKABLE

    def desk_of(self, seat: Pos) -> Pos:
        return (seat[0], seat[1] - 1)

    def find_path(self, start: Pos, goal: Pos) -> Optional[List[Pos]]:
        """BFS (4 yön). Başlangıç hariç, hedef dahil adım listesi; yol yoksa None."""
        if start == goal:
            return []
        if not self.walkable(*goal):
            return None
        prev: Dict[Pos, Optional[Pos]] = {start: None}
        q = deque([start])
        while q:
            cur = q.popleft()
            if cur == goal:
                break
            cx, cy = cur
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                n = (nx, ny)
                if n not in prev and self.walkable(nx, ny):
                    prev[n] = cur
                    q.append(n)
        if goal not in prev:
            return None
        path: List[Pos] = []
        node: Optional[Pos] = goal
        while node is not None and node != start:
            path.append(node)
            node = prev[node]
        path.reverse()
        return path

    # ------------------------------------------------------------ çizim
    def draw(self, buf, ox: int, oy: int, env: MapEnv) -> None:
        for y in range(self.h):
            for x in range(self.w):
                top, bot = self._sprite(x, y, env)
                px, py = ox + x * TW, oy + y * TH
                for i in range(TW):
                    ch, f, b = top[i]
                    buf.put(px + i, py, ch, f, b)
                    ch, f, b = bot[i]
                    buf.put(px + i, py + 1, ch, f, b)

    def _floor(self, x: int, y: int) -> Tuple[List[Cell], List[Cell]]:
        b = C.FLOOR_A if (x + y) % 2 == 0 else C.FLOOR_B
        return ([(" ", C.GROUT, b)] * 3, [("▁", C.GROUT, b)] * 3)

    def _under(self, x: int, y: int) -> RGB:
        """Eşyaların altındaki zemin rengi."""
        t = self.grid[y][x]
        if t in (Tile.SERVER,):
            return C.SERVER_FLOOR
        return C.FLOOR_A if (x + y) % 2 == 0 else C.FLOOR_B

    def _sprite(self, x: int, y: int, env: MapEnv) -> Tuple[List[Cell], List[Cell]]:
        t = self.grid[y][x]
        tt = env.t
        if t == Tile.FLOOR:
            return self._floor(x, y)
        if t == Tile.WALL:
            return ([(" ", C.WALL_TOP, C.WALL_TOP)] * 3, [("▁", shade(C.WALL_FACE, 0.8), C.WALL_FACE)] * 3)
        if t == Tile.WINDOW:
            sky = C.gradient(SKY_STOPS, env.day_frac)
            low = mix(sky, (255, 255, 255), 0.25)
            return ([(" ", sky, sky), ("┃", C.WALL_TOP, sky), (" ", sky, sky)],
                    [("▁", C.WALL_TOP, low), ("┃", C.WALL_TOP, low), ("▁", C.WALL_TOP, low)])
        if t == Tile.CARPET:
            b = C.CARPET if (x + y) % 2 == 0 else shade(C.CARPET, 0.94)
            return ([("░", C.CARPET_HI, b)] * 3, [(" ", C.CARPET_HI, b), ("░", C.CARPET_HI, b), (" ", C.CARPET_HI, b)])
        if t == Tile.RUG:
            b = C.RUG if (x + y) % 2 == 0 else shade(C.RUG, 0.94)
            return ([("░", C.RUG_HI, b)] * 3, [(" ", C.RUG_HI, b), ("░", C.RUG_HI, b), (" ", C.RUG_HI, b)])
        if t == Tile.SFLOOR:
            b = C.SERVER_FLOOR if (x + y) % 2 == 0 else shade(C.SERVER_FLOOR, 1.15)
            if env.alert:
                b = mix(b, (120, 20, 20), 0.35 + 0.25 * math.sin(tt * 9))
            return ([(" ", b, b)] * 3, [("▁", shade(b, 0.7), b)] * 3)
        if t == Tile.DESK:
            return self._desk(x, y, env)
        if t == Tile.SEAT:
            fl = self._under(x, y)
            col = (30, 120, 130) if "chairs" in env.upgrades else (38, 42, 56)
            return ([("▟", col, fl), ("█", col, fl), ("▙", col, fl)],
                    [(" ", col, fl), ("╨", shade(col, 1.5), fl), (" ", col, fl)])
        if t in (Tile.COFFEE, Tile.BAR):
            return self._coffee(x, y, env, t == Tile.BAR)
        if t == Tile.WATER:
            fl = self._under(x, y)
            return ([("▟", C.WATER_COL, fl), ("█", mix(C.WATER_COL, (255, 255, 255), 0.2 + 0.2 * math.sin(tt * 2)), fl), ("▙", C.WATER_COL, fl)],
                    [("▐", (200, 206, 220), fl), ("█", (226, 230, 240), fl), ("▌", (200, 206, 220), fl)])
        if t == Tile.PLANT:
            fl = self._under(x, y)
            sway = math.sin(tt * 1.4 + x) > 0.6
            return ([("▟" if not sway else "▜", C.LEAF, fl), ("▓", C.LEAF_HI, fl), ("▙" if not sway else "▛", C.LEAF, fl)],
                    [("▝", C.POT, fl), ("█", C.POT, fl), ("▘", C.POT, fl)])
        if t == Tile.SERVER:
            return self._server(x, y, env)
        if t == Tile.TABLE:
            top_b = C.WOOD_HI if self.grid[y][x - 1] != Tile.TABLE else mix(C.WOOD_HI, C.WHITE, 0.15)
            return ([(" ", top_b, C.WOOD_HI)] * 3, [("▁", C.WOOD_DARK, C.WOOD)] * 3)
        if t == Tile.COUCH:
            return ([("▄", shade(C.COUCH, 0.7), C.COUCH_HI)] * 3, [(" ", C.COUCH, C.COUCH)] * 3)
        if t == Tile.ARCADE:
            hue = (tt * 80) % 360
            fl = C.RUG if (x + y) % 2 == 0 else shade(C.RUG, 0.94)
            return ([("▐", (50, 50, 70), fl), ("▓", C.hsv(hue, 0.9, 1.0), fl), ("▌", (50, 50, 70), fl)],
                    [("▐", (50, 50, 70), fl), ("▪", C.GOLD, fl), ("▌", (50, 50, 70), fl)])
        return self._floor(x, y)

    def _desk(self, x: int, y: int, env: MapEnv) -> Tuple[List[Cell], List[Cell]]:
        active = (x, y) in env.active_desks
        dual = "monitors" in env.upgrades
        phase = int(env.t * 7 + x * 3 + y) % 4
        if active:
            glow = mix(C.MONITOR_ON, (120, 255, 200), 0.5 * ((phase % 2)))
            scr = "▓▒░█"[phase]
        else:
            glow = C.MONITOR_OFF
            scr = "▓"
        frame = (34, 38, 48)
        if dual:
            top = [("█", glow, C.WOOD), ("▐", frame, C.WOOD), ("█", glow if active else C.MONITOR_OFF, C.WOOD)]
        else:
            top = [("▐", frame, C.WOOD), (scr, glow, frame), ("▌", frame, C.WOOD)]
        bot = [("═", (214, 218, 228), C.WOOD_HI), ("═", (214, 218, 228), C.WOOD_HI), ("●", (250, 240, 220), C.WOOD_HI)]
        if (x + y) % 3 == 0:
            bot[2] = ("c", (240, 240, 240), C.WOOD_HI)
        return top, bot

    def _coffee(self, x: int, y: int, env: MapEnv, bar: bool):
        led = (60, 255, 120)
        if env.coffee_broken:
            led = (255, 40, 40) if int(env.t * 3) % 2 == 0 else (90, 20, 20)
        body = (212, 170, 60) if bar else C.STEEL
        fl = C.WOOD_DARK
        return ([("▐", body, fl), ("█", C.COFFEE_COL if not env.coffee_broken else (110, 70, 60), fl), ("●", led, fl)],
                [("▀", C.WOOD_HI, C.WOOD), ("▃", (245, 245, 245), C.WOOD), ("▀", C.WOOD_HI, C.WOOD)])

    def _server(self, x: int, y: int, env: MapEnv):
        fl = C.SERVER_FLOOR
        if env.alert:
            fl = mix(fl, (150, 30, 20), 0.5 + 0.4 * math.sin(env.t * 9))
        def led(k: int) -> RGB:
            if env.alert:
                return (255, 60, 40) if int(env.t * 6 + k) % 2 == 0 else (110, 20, 10)
            v = int(env.t * 4 + x * 2 + k * 3) % 5
            return [(80, 255, 140), (80, 200, 255), (255, 200, 60), (80, 255, 140), (60, 90, 80)][v]
        return ([("▐", C.STEEL, fl), ("≡", led(0), C.STEEL_DARK), ("▌", C.STEEL, fl)],
                [("▐", C.STEEL, fl), ("▪", led(1), C.STEEL_DARK), ("▌", C.STEEL, fl)])
