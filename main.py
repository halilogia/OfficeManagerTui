"""Office Manager Tycoon TUI — ana döngü, klavye girişi, 30 FPS yenileme.

Çalıştır:  python main.py   (Windows Terminal önerilir, en az 125x38)
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional

import colors as C
from renderer import SCREEN_H, SCREEN_W, DiffWriter, Renderer, UIState
from simulation import UPGRADES, Simulation

try:
    import msvcrt
except ImportError:  # Windows dışı
    msvcrt = None

FPS = 30
SPEEDS = {1: 1, 2: 2, 3: 4}
ARROWS = {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}


class Game:
    """Simülasyon + arayüz durumu; terminalden bağımsız olduğu için headless test edilebilir."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self.sim = Simulation(seed)
        self.ui = UIState()
        self.seed = seed

    # ------------------------------------------------------------ giriş
    def selected_worker(self):
        ws = self.sim.workers
        return ws[min(self.ui.selected, len(ws) - 1)] if ws else None

    def _result(self, res) -> None:
        ok, msg = res
        self.ui.flash(msg, C.GOOD if ok else C.BAD)

    def handle_key(self, key: str) -> bool:
        """False dönerse oyundan çıkılır."""
        ui, sim = self.ui, self.sim
        if key == "CTRL_C":
            return False
        if sim.game_over:
            if key == "r":
                self.__init__(self.seed)
            return key != "q"
        if ui.mode != "normal":
            self._modal_key(key)
            return True
        n = len(sim.workers)
        if key == "q":
            return False
        if key == "SPACE":
            ui.paused = not ui.paused
        elif key in SPEEDS_KEYS:
            ui.speed = SPEEDS[int(key)]
            ui.flash(f"Hız: {ui.speed}x", C.ACCENT, 1.5)
        elif key in ("TAB", "RIGHT", "DOWN") and n:
            ui.selected = (ui.selected + 1) % n
        elif key in ("LEFT", "UP") and n:
            ui.selected = (ui.selected - 1) % n
        elif key == "h":
            ui.mode, ui.cursor = "hire", 0
        elif key == "f" and n:
            ui.mode = "fire"
        elif key == "p":
            ui.mode, ui.cursor = "project", 0
        elif key == "b" and n:
            ui.mode, ui.cursor = "bonus", 0
        elif key == "u":
            ui.mode, ui.cursor = "upgrade", 0
        elif key == "c":
            self._result(sim.order_snacks())
        elif key == "m":
            self._result(sim.call_meeting())
        elif key == "k":
            self._result(sim.toggle_crunch())
        return True

    def _modal_key(self, key: str) -> None:
        ui, sim = self.ui, self.sim
        mode = ui.mode
        size = {"hire": len(sim.candidates), "project": len(sim.offers), "bonus": 2,
                "upgrade": len(UPGRADE_KEYS)}.get(mode, 0)
        if key == "ESC" or (mode == "fire" and key == "n"):
            ui.mode = "normal"
            return
        if mode == "fire":
            if key == "y":
                w = self.selected_worker()
                if w is not None:
                    self._result(sim.fire(w))
                    ui.selected = max(0, min(ui.selected, len(sim.workers) - 1))
                ui.mode = "normal"
            return
        if key == "UP" and size:
            ui.cursor = (ui.cursor - 1) % size
        elif key == "DOWN" and size:
            ui.cursor = (ui.cursor + 1) % size
        elif mode == "hire" and key == "r":
            self._result(sim.reroll_candidates())
            ui.cursor = 0
        elif key == "ENTER" or (key.isdigit() and 1 <= int(key) <= size):
            idx = ui.cursor if key == "ENTER" else int(key) - 1
            if not 0 <= idx < size:
                return
            if mode == "hire":
                self._result(sim.hire(idx))
                ui.cursor = max(0, min(ui.cursor, len(sim.candidates) - 1))
            elif mode == "project":
                res = sim.start_project(idx)
                self._result(res)
                if res[0]:
                    ui.mode = "normal"
            elif mode == "bonus":
                self._result(sim.give_bonus("one" if idx == 0 else "all", self.selected_worker()))
                ui.mode = "normal"
            elif mode == "upgrade":
                self._result(sim.buy_upgrade(UPGRADE_KEYS[idx]))

    # ------------------------------------------------------------ zaman
    def update(self, real_dt: float) -> None:
        ui = self.ui
        if ui.flash_t > 0:
            ui.flash_t -= real_dt
        if ui.paused or ui.mode != "normal":
            return
        dt = real_dt * ui.speed
        while dt > 1e-6:
            step = min(dt, 0.05)
            self.sim.update(step)
            dt -= step
        ui.selected = max(0, min(ui.selected, len(self.sim.workers) - 1))


UPGRADE_KEYS = list(UPGRADES)
SPEEDS_KEYS = {"1", "2", "3"}


# ====================================================================== terminal
def read_key() -> Optional[str]:
    if msvcrt is None or not msvcrt.kbhit():
        return None
    ch = msvcrt.getwch()
    if ch in ("\x00", "\xe0"):
        return ARROWS.get(msvcrt.getwch())
    if ch == "\x03":
        return "CTRL_C"
    if ch == "\x1b":
        return "ESC"
    if ch in ("\r", "\n"):
        return "ENTER"
    if ch == "\t":
        return "TAB"
    if ch == " ":
        return "SPACE"
    return ch.lower()


def term_size():
    try:
        s = os.get_terminal_size()
        return s.columns, s.lines
    except OSError:
        return SCREEN_W, SCREEN_H


def run() -> int:
    if msvcrt is None:
        print("Bu oyun Windows terminali (msvcrt) için yazıldı.")
        return 1
    C.enable_vt()
    out = sys.stdout
    game = Game()
    renderer = Renderer()
    writer = DiffWriter(out)
    out.write(C.ALT_ON + C.HIDE_CURSOR + C.CLEAR)
    out.flush()
    last = time.perf_counter()
    last_size = None
    running = True
    try:
        while running:
            now = time.perf_counter()
            dt = min(now - last, 0.1)
            last = now
            while True:
                key = read_key()
                if key is None:
                    break
                if not game.handle_key(key):
                    running = False
                    break
            if not running:
                break
            game.update(dt)
            size = term_size()
            if size != last_size:
                last_size = size
                writer.invalidate()
                out.write(C.RESET + C.CLEAR)
            if size[0] < SCREEN_W or size[1] < SCREEN_H:
                msg = f"Terminal çok küçük: {size[0]}x{size[1]}  (gerekli {SCREEN_W}x{SCREEN_H})"
                out.write(f"{C.HOME}{C.RESET}{msg}")
                out.flush()
                writer.invalidate()
            else:
                writer.flush(renderer.render(game.sim, game.ui, dt))
            spare = 1.0 / FPS - (time.perf_counter() - now)
            if spare > 0:
                time.sleep(spare)
    except KeyboardInterrupt:
        pass
    finally:
        out.write(C.RESET + C.SHOW_CURSOR + C.ALT_OFF)
        out.flush()
    print(f"Oyun bitti. Gün {game.sim.day}, bütçe ${game.sim.funds:,}, teslim edilen sprint {game.sim.delivered}.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
