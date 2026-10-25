"""Headless test paketi: python test_office.py  (veya python -m unittest)."""
import io
import unittest

import colors as C
from main import Game
from office_map import MAP_H, MAP_W, OfficeMap, Tile
from renderer import SCREEN_H, SCREEN_W, DiffWriter, Renderer, ScreenBuffer, UIState
from simulation import DAY_LEN, UPGRADES, Simulation
from worker import Role, State


def run(sim, secs, dt=0.05):
    for _ in range(int(secs / dt)):
        sim.update(dt)


class TestColors(unittest.TestCase):
    def test_escape_codes(self):
        self.assertEqual(C.fg((1, 2, 3)), "\033[38;2;1;2;3m")
        self.assertEqual(C.bg((4, 5, 6)), "\033[48;2;4;5;6m")

    def test_mix_and_width(self):
        self.assertEqual(C.mix((0, 0, 0), (100, 200, 50), 0.5), (50, 100, 25))
        self.assertEqual(C.cw("🔥"), 2)
        self.assertEqual(C.cw("a"), 1)


class TestBuffer(unittest.TestCase):
    def test_wide_char_and_diff(self):
        buf = ScreenBuffer(10, 2)
        buf.put(2, 0, "🔥", C.BAD)
        self.assertEqual(buf.ch[2], "🔥")
        self.assertEqual(buf.ch[3], "")
        buf.put(3, 0, "x")                      # geniş karakterin yarısını ezmek
        self.assertEqual(buf.ch[2], " ")
        out = io.StringIO()
        w = DiffWriter(out)
        self.assertGreater(w.flush(buf), 0)
        self.assertEqual(w.flush(buf), 0)       # değişiklik yok -> hiçbir şey yazma
        buf.put(0, 1, "A", C.WARN)
        n = w.flush(buf)
        self.assertTrue(0 < n < 120)
        self.assertIn("\033[2;1H", out.getvalue())

    def test_text_clip(self):
        buf = ScreenBuffer(10, 1)
        end = buf.text(0, 0, "abcdefghijklmnop", clip=5)
        self.assertEqual(end, 5)
        self.assertEqual(buf.dump(), "abcde")


class TestMap(unittest.TestCase):
    def setUp(self):
        self.m = OfficeMap()

    def test_walls_and_items_block(self):
        self.assertFalse(self.m.walkable(0, 0))
        self.assertFalse(self.m.walkable(3, 1))     # kahve makinesi
        self.assertFalse(self.m.walkable(2, 6))     # masa
        self.assertTrue(self.m.walkable(2, 7))      # koltuk
        self.assertIsNone(self.m.find_path((1, 5), (0, 0)))

    def test_seats_and_spots_reachable(self):
        self.assertEqual(len(self.m.seats), 12)
        for s in self.m.seats:
            self.assertIsNotNone(self.m.find_path(self.m.entrance, s), s)
        for kind, spots in self.m.spots.items():
            for sp in spots:
                self.assertTrue(self.m.walkable(*sp), (kind, sp))
                p = self.m.find_path((2, 7), sp)
                self.assertIsNotNone(p, (kind, sp))

    def test_path_is_contiguous(self):
        path = self.m.find_path((2, 7), (25, 3))
        cur = (2, 7)
        for step in path:
            self.assertEqual(abs(step[0] - cur[0]) + abs(step[1] - cur[1]), 1)
            self.assertTrue(self.m.walkable(*step))
            cur = step
        self.assertEqual(cur, (25, 3))

    def test_upgrade_places_tile(self):
        self.m.apply_upgrade("arcade")
        self.assertEqual(self.m.grid[9][27], Tile.ARCADE)
        self.assertFalse(self.m.walkable(27, 9))
        self.assertEqual((MAP_W, MAP_H), (30, 12))


class TestWorkers(unittest.TestCase):
    def test_start_roster_and_work(self):
        sim = Simulation(1)
        roles = {w.role for w in sim.workers}
        self.assertEqual(roles, set(Role))
        p0 = sim.projects[0].progress
        run(sim, 10)
        self.assertGreater(sim.projects[0].progress, p0)
        for w in sim.workers:
            self.assertTrue(0 <= w.morale <= 100 and 0 <= w.energy <= 100)

    def test_coffee_run_restores_energy(self):
        sim = Simulation(2)
        sim.event_t = 9999
        w = sim.workers[0]
        w.energy = 20
        w.decide_t = 0
        seen = set()
        for _ in range(900):
            sim.update(0.05)
            seen.add(w.state)
            w.decide_t = min(w.decide_t, 0.1)
            if State.COFFEE_RUN in seen and w.state is State.WORKING and w.seated:
                break
        self.assertTrue({State.COFFEE_RUN} <= seen or {State.LOUNGE} <= seen)
        self.assertGreater(w.energy, 30)
        self.assertTrue(w.seated)

    def test_sleeping_and_stress(self):
        sim = Simulation(3)
        sim.event_t = 9999
        w = sim.workers[1]
        w.energy = 3
        w.decide_t = 0
        run(sim, 2)
        self.assertIs(w.state, State.SLEEPING)
        w.state, w.energy = State.WORKING, 80
        base = w.rate(sim)
        w.state = State.STRESSED
        self.assertAlmostEqual(w.rate(sim), base * 0.2, places=6)

    def test_burnout_state_triggers(self):
        sim = Simulation(4)
        sim.event_t = 9999
        w = sim.workers[2]
        w.morale, w.decide_t = 10, 0
        run(sim, 3)
        self.assertIs(w.state, State.STRESSED)

    def test_panic_and_resolve(self):
        sim = Simulation(5)
        sim.event_t = 9999
        sim.trigger_event("server")
        self.assertIsNotNone(sim.alert)
        run(sim, 6)
        self.assertTrue(any(w.state is State.PANIC for w in sim.workers))
        run(sim, 40)
        self.assertIsNone(sim.alert)
        run(sim, 8)
        self.assertFalse(any(w.state is State.PANIC for w in sim.workers))

    def test_celebration_on_delivery(self):
        sim = Simulation(6)
        sim.event_t = 9999
        p = sim.projects[0]
        for r in p.needs:
            p.needs[r] = 0.0
        funds = sim.funds
        sim.update(0.05)
        self.assertEqual(sim.delivered, 1)
        self.assertGreater(sim.funds, funds)
        self.assertTrue(any(w.state is State.CELEBRATING for w in sim.workers))

    def test_chat_at_cooler(self):
        sim = Simulation(7)
        sim.event_t = 9999
        for w in sim.workers[:2]:
            w.social, w.social_limit, w.decide_t = 999, 1, 0
        seen = set()
        for _ in range(400):
            sim.update(0.05)
            seen |= {w.state for w in sim.workers}
        self.assertIn(State.WATER_COOLER_CHAT, seen)


class TestSimulation(unittest.TestCase):
    def test_hire_fire(self):
        sim = Simulation(10)
        n, funds = len(sim.workers), sim.funds
        fee = sim.candidates[0].fee
        ok, _ = sim.hire(0)
        self.assertTrue(ok)
        self.assertEqual(len(sim.workers), n + 1)
        self.assertEqual(sim.funds, funds - fee)
        w = sim.workers[-1]
        self.assertTrue(sim.fire(w)[0])
        self.assertEqual(len(sim.workers), n)
        sim.funds = 0
        self.assertFalse(sim.hire(0)[0])

    def test_hire_cap(self):
        sim = Simulation(11)
        sim.funds = 10 ** 6
        while len(sim.workers) < 10:
            sim.new_candidates()
            self.assertTrue(sim.hire(0)[0])
        self.assertFalse(sim.hire(0)[0])

    def test_actions(self):
        sim = Simulation(12)
        sim.funds = 20000
        for w in sim.workers:
            w.morale, w.energy = 30, 30
        self.assertTrue(sim.give_bonus("all")[0])
        self.assertTrue(all(w.morale == 50 for w in sim.workers))
        self.assertTrue(sim.order_snacks()[0])
        self.assertTrue(all(w.energy == 65 for w in sim.workers))
        self.assertTrue(sim.give_bonus("one", sim.workers[0])[0])
        self.assertTrue(sim.call_meeting()[0])
        self.assertFalse(sim.call_meeting()[0])
        self.assertTrue(sim.toggle_crunch()[0] and sim.crunch)

    def test_crunch_is_faster_and_drains(self):
        a, b = Simulation(13), Simulation(13)
        for s in (a, b):
            s.event_t = 9999
        b.toggle_crunch()
        run(a, 15)
        run(b, 15)
        self.assertGreater(b.projects[0].done, a.projects[0].done * 1.5)
        self.assertLess(sum(w.energy for w in b.workers), sum(w.energy for w in a.workers))

    def test_upgrades(self):
        sim = Simulation(14)
        sim.funds = 50000
        for k in UPGRADES:
            self.assertTrue(sim.buy_upgrade(k)[0])
            self.assertFalse(sim.buy_upgrade(k)[0])
        self.assertEqual(sim.upgrades, set(UPGRADES))
        sim.funds = 0
        self.assertFalse(Simulation(1).buy_upgrade("monitors") == (True, ""))

    def test_projects(self):
        sim = Simulation(15)
        self.assertTrue(sim.start_project(0)[0])
        self.assertTrue(sim.start_project(0)[0])
        self.assertFalse(sim.start_project(0)[0])       # en fazla 3
        self.assertEqual(len(sim.projects), 3)

    def test_day_cycle_and_finance(self):
        sim = Simulation(16)
        sim.event_t = 9999
        start = sim.funds
        run(sim, DAY_LEN + 1)
        self.assertEqual(sim.day, 2)
        self.assertLess(sim.funds, start + 1)           # maaşlar kesildi
        self.assertIn("Gün 1", sim.last_report)

    def test_all_events(self):
        for name in ("server", "coffee", "donut", "prodbug", "innovation", "client", "flu"):
            sim = Simulation(17)
            sim.trigger_event(name)
            run(sim, 5)
            self.assertTrue(len(sim.log) >= 2, name)

    def test_long_run_is_stable(self):
        for seed in (1, 2, 3):
            sim = Simulation(seed)
            run(sim, DAY_LEN * 6, dt=0.1)
            self.assertFalse(sim.game_over, f"seed {seed}: {sim.game_over} funds={sim.funds}")
            self.assertGreaterEqual(sim.day, 6)

    def test_bankruptcy(self):
        sim = Simulation(18)
        sim.funds = -4000
        sim.update(0.05)
        self.assertTrue(sim.game_over)

    def test_determinism(self):
        a, b = Simulation(99), Simulation(99)
        run(a, 60)
        run(b, 60)
        self.assertEqual(a.funds, b.funds)
        self.assertEqual([w.pos for w in a.workers], [w.pos for w in b.workers])


class TestRenderAndGame(unittest.TestCase):
    def test_render_frame_all_modes(self):
        g = Game(20)
        r = Renderer()
        g.sim.trigger_event("server")
        g.sim.trigger_event("donut")
        for mode in ("normal", "hire", "project", "bonus", "upgrade", "fire"):
            g.ui.mode = mode
            for _ in range(5):
                g.sim.update(0.05)
                buf = r.render(g.sim, g.ui, 1 / 30)
            self.assertEqual((buf.w, buf.h), (SCREEN_W, SCREEN_H))
        text = buf.dump()
        self.assertIn("İŞTEN ÇIKARMA", text)
        g.ui.mode = "normal"
        text = r.render(g.sim, g.ui, 1 / 30).dump()
        for needle in ("OFFICE MANAGER TYCOON", "SPRINTLER", "EKİP", "KOMUTLAR", "OLAY GÜNLÜĞÜ"):
            self.assertIn(needle, text)

    def test_diffwriter_whole_game(self):
        g = Game(21)
        r = Renderer()
        out = io.StringIO()
        w = DiffWriter(out)
        first = w.flush(r.render(g.sim, g.ui, 1 / 30))
        g.update(1 / 30)
        second = w.flush(r.render(g.sim, g.ui, 1 / 30))
        self.assertGreater(first, 10000)
        self.assertLess(second, first)

    def test_keys(self):
        g = Game(22)
        n = len(g.sim.workers)
        g.sim.funds = 50000
        self.assertTrue(g.handle_key("SPACE"))
        self.assertTrue(g.ui.paused)
        g.handle_key("SPACE")
        g.handle_key("3")
        self.assertEqual(g.ui.speed, 4)
        g.handle_key("1")
        self.assertEqual(g.ui.speed, 1)
        g.handle_key("RIGHT")
        self.assertEqual(g.ui.selected, 1)
        g.handle_key("h")
        self.assertEqual(g.ui.mode, "hire")
        g.handle_key("1")
        self.assertEqual(len(g.sim.workers), n + 1)
        g.handle_key("ESC")
        self.assertEqual(g.ui.mode, "normal")
        g.handle_key("f")
        self.assertEqual(g.ui.mode, "fire")
        g.handle_key("y")
        self.assertEqual(len(g.sim.workers), n)
        g.handle_key("u")
        g.handle_key("2")
        self.assertIn("monitors", g.sim.upgrades)
        g.handle_key("ESC")
        g.handle_key("p")
        g.handle_key("ENTER")
        self.assertEqual(len(g.sim.projects), 2)
        g.handle_key("b")
        g.handle_key("2")
        g.handle_key("c")
        g.handle_key("m")
        g.handle_key("k")
        self.assertTrue(g.sim.crunch)
        paused_before = g.sim.total_time
        g.handle_key("h")
        g.update(0.5)                                   # menü açıkken sim durur
        self.assertEqual(g.sim.total_time, paused_before)
        g.handle_key("ESC")
        self.assertFalse(g.handle_key("q"))

    def test_game_over_restart(self):
        g = Game(23)
        g.sim.funds = -5000
        g.update(0.1)
        self.assertTrue(g.sim.game_over)
        Renderer().render(g.sim, g.ui, 0.03)
        self.assertTrue(g.handle_key("r"))
        self.assertFalse(g.sim.game_over)


if __name__ == "__main__":
    unittest.main(verbosity=1)
