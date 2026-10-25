"""Şirket simülasyonu: bütçe, projeler, yükseltmeler, rastgele olaylar ve yönetici aksiyonları."""
from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Set, Tuple

import colors as C
from office_map import OfficeMap
from worker import (HAIR, ROLE_INFO, SKIN, Role, State, Worker, make_name,
                    salary_for)

DAY_LEN = 100.0          # bir iş günü (sim saniyesi)
START_FUNDS = 9000
BANKRUPT_AT = -3000
GOAL_FUNDS = 40000
MAX_WORKERS = 10
MAX_PROJECTS = 3
RENT = 220

UPGRADES = {
    "chairs": ("Ergonomik Koltuklar", 2500, "Enerji tüketimi -%25"),
    "monitors": ("Çift Monitör", 4000, "İş çıktısı +%20"),
    "arcade": ("Langırt / Arcade", 3000, "Dinlenme alanında moral artışı"),
    "coffee_bar": ("Kahve Barı", 2000, "Daha hızlı ve güçlü kahve"),
    "servers": ("Soğutmalı Sunucu Odası", 3500, "Sunucu krizi riski -%60"),
}

TEMPLATES: Dict[str, Dict[Role, float]] = {
    "Mobil Uygulama v2": {Role.FRONTEND: .30, Role.BACKEND: .25, Role.UIUX: .20, Role.DEVOPS: .08, Role.MARKETING: .07, Role.INTERN: .10},
    "AI Çeviri Motoru": {Role.BACKEND: .42, Role.DEVOPS: .18, Role.FRONTEND: .12, Role.UIUX: .08, Role.MARKETING: .05, Role.INTERN: .15},
    "E-Ticaret Platformu": {Role.FRONTEND: .26, Role.BACKEND: .26, Role.UIUX: .14, Role.DEVOPS: .10, Role.MARKETING: .16, Role.INTERN: .08},
    "Oyun Sunucusu": {Role.BACKEND: .45, Role.DEVOPS: .25, Role.FRONTEND: .08, Role.UIUX: .05, Role.MARKETING: .02, Role.INTERN: .15},
    "CRM Panosu": {Role.FRONTEND: .30, Role.UIUX: .25, Role.BACKEND: .22, Role.MARKETING: .08, Role.DEVOPS: .05, Role.INTERN: .10},
    "Fintech Portalı": {Role.BACKEND: .35, Role.DEVOPS: .20, Role.FRONTEND: .18, Role.UIUX: .12, Role.MARKETING: .05, Role.INTERN: .10},
    "Akıllı Ev Uygulaması": {Role.FRONTEND: .25, Role.BACKEND: .22, Role.DEVOPS: .18, Role.UIUX: .15, Role.MARKETING: .10, Role.INTERN: .10},
    "Chatbot Asistanı": {Role.BACKEND: .32, Role.UIUX: .18, Role.FRONTEND: .18, Role.MARKETING: .12, Role.DEVOPS: .08, Role.INTERN: .12},
    "Veri Ambarı": {Role.BACKEND: .38, Role.DEVOPS: .30, Role.FRONTEND: .08, Role.UIUX: .04, Role.MARKETING: .03, Role.INTERN: .17},
}


@dataclass
class Project:
    name: str
    size: float
    reward: int
    deadline_day: int
    needs: Dict[Role, float]
    quality: float = 60.0
    bugs: float = 0.0
    done: float = 0.0

    def remaining(self) -> float:
        return sum(v for v in self.needs.values() if v > 0)

    @property
    def progress(self) -> float:
        return max(0.0, min(1.0, 1.0 - self.remaining() / self.size))


@dataclass
class Candidate:
    name: str
    role: Role
    skill: int
    salary: int
    skin: Tuple[int, int, int]
    hair: Tuple[int, int, int]

    @property
    def fee(self) -> int:
        return self.salary * 2


@dataclass
class Alert:
    id: int
    kind: str
    title: str
    need: float
    timer: float
    total: float
    progress: float = 0.0


@dataclass
class Banner:
    text: str
    color: C.RGB
    ttl: float = 7.0


EVENT_WEIGHTS = [("server", 3.0), ("coffee", 2.5), ("donut", 3.0), ("prodbug", 2.5),
                 ("innovation", 2.0), ("client", 1.5), ("flu", 1.2)]


class Simulation:
    def __init__(self, seed: Optional[int] = None) -> None:
        self.rng = random.Random(seed)
        self.office = OfficeMap()
        self.workers: List[Worker] = []
        self.projects: List[Project] = []
        self.offers: List[Project] = []
        self.candidates: List[Candidate] = []
        self.upgrades: Set[str] = set()
        self.log: Deque[Tuple[str, str, C.RGB]] = deque(maxlen=80)
        self.fx: List[Tuple[str, object]] = []
        self.banner: Optional[Banner] = None
        self.alert: Optional[Alert] = None
        self._alert_id = 0
        self._wid = 0
        self.funds = START_FUNDS
        self.day = 1
        self.tod = 0.0
        self.total_time = 0.0
        self.crunch = False
        self.coffee_broken = 0.0
        self.innovation_t = 0.0
        self.meeting_t = 0.0
        self.meeting_cd = 0.0
        self.celebrate_t = 0.0
        self.event_t = self.rng.uniform(18, 28)
        self.idle_warn = 0.0
        self.income_today = 0
        self.cups_today = 0
        self.delivered = 0
        self.last_report = ""
        self.game_over = ""
        self.won = False
        self._seed_team()
        self.projects.append(self._make_project("Mobil Uygulama v2", size=1000, days=6))
        self.new_offers()
        self.new_candidates()
        self.say_log("Hoş geldin müdür! Ekibin hazır, ilk sprint başladı.", C.ACCENT)

    # ------------------------------------------------------------ ctx arayüzü
    def has(self, key: str) -> bool:
        return key in self.upgrades

    def claim_spot(self, kind: str, worker: Worker):
        taken = {w.target for w in self.workers if w is not worker and w.target is not None}
        free = [s for s in self.office.spots[kind] if s not in taken]
        if not free:
            return None
        if kind in ("server", "meeting"):
            return self.rng.choice(free)
        return min(free, key=lambda s: abs(s[0] - worker.pos[0]) + abs(s[1] - worker.pos[1]))

    def nearby_chatters(self, worker: Worker) -> List[Worker]:
        return [w for w in self.workers
                if w is not worker and w.state is State.WATER_COOLER_CHAT and w.phase == "act"
                and abs(w.pos[0] - worker.pos[0]) + abs(w.pos[1] - worker.pos[1]) <= 2]

    def on_coffee(self, worker: Worker) -> None:
        self.cups_today += 1

    # ------------------------------------------------------------ yardımcılar
    @property
    def clock(self) -> str:
        mins = int(9 * 60 + 9 * 60 * self.tod / DAY_LEN)
        return f"{mins // 60:02d}:{mins % 60:02d}"

    @property
    def day_frac(self) -> float:
        return self.tod / DAY_LEN

    def say_log(self, text: str, color: C.RGB = C.TEXT) -> None:
        self.log.append((self.clock, text, color))

    def announce(self, text: str, color: C.RGB, ttl: float = 7.0) -> None:
        self.banner = Banner(text, color, ttl)
        self.say_log(text, color)

    def avg_morale(self) -> float:
        return sum(w.morale for w in self.workers) / len(self.workers) if self.workers else 0.0

    def daily_burn(self) -> int:
        return sum(w.salary for w in self.workers) + RENT + 40 * len(self.upgrades) + 5 * len(self.workers)

    def _free_seat(self):
        used = {w.seat for w in self.workers}
        for s in self.office.seats:
            if s not in used:
                return s
        return None

    def _new_worker(self, name, role, skill, salary, skin, hair, at_entrance=False) -> Worker:
        self._wid += 1
        seat = self._free_seat()
        w = Worker(self._wid, name, role, skill, salary, seat, skin, hair,
                   morale=self.rng.uniform(65, 85), energy=self.rng.uniform(70, 100))
        w.social_limit = self.rng.uniform(30, 90)
        if at_entrance:
            w.pos = w.prev = self.office.entrance
        self.workers.append(w)
        return w

    def _seed_team(self) -> None:
        for role, skill in ((Role.BACKEND, 6), (Role.FRONTEND, 5), (Role.UIUX, 5),
                            (Role.DEVOPS, 5), (Role.MARKETING, 4), (Role.INTERN, 2)):
            self._new_worker(make_name(self.rng), role, skill, salary_for(role, skill),
                             self.rng.choice(SKIN), self.rng.choice(HAIR))

    # ------------------------------------------------------------ projeler
    def _make_project(self, name: str, size: Optional[float] = None, days: Optional[int] = None) -> Project:
        size = size or self.rng.choice([800, 1000, 1200, 1500, 1800, 2200])
        weights = TEMPLATES[name]
        cap = max(100.0, sum(w.rate_estimate() for w in self.workers) * DAY_LEN) if self.workers else 300.0
        days = days or max(3, int(math.ceil(size / cap * 1.5)))
        reward = int(size * self.rng.uniform(6.8, 8.6))
        return Project(name, size, reward, self.day + days, {r: size * f for r, f in weights.items()})

    def new_offers(self) -> None:
        active = {p.name for p in self.projects}
        names = [n for n in TEMPLATES if n not in active]
        self.rng.shuffle(names)
        self.offers = [self._make_project(n) for n in names[:3]]

    def start_project(self, index: int):
        if len(self.projects) >= MAX_PROJECTS:
            return False, "En fazla 3 aktif sprint yürütülebilir."
        if not 0 <= index < len(self.offers):
            return False, "Geçersiz teklif."
        p = self.offers.pop(index)
        p.deadline_day = self.day + max(2, p.deadline_day - self.day)
        self.projects.append(p)
        self.say_log(f"Yeni sprint: {p.name} (${p.reward:,})", C.ACCENT)
        self.new_offers()
        return True, f"Sprint başladı: {p.name}"

    def _contribute(self, w: Worker, pts: float) -> None:
        for p in self.projects:
            if p.needs.get(w.role, 0) > 0:
                self._apply(p, w, pts, w.role, 1.0)
                return
        for p in self.projects:
            open_roles = [r for r, v in p.needs.items() if v > 0]
            if open_roles:
                self._apply(p, w, pts, max(open_roles, key=lambda r: p.needs[r]), 0.4)
                return

    def _apply(self, p: Project, w: Worker, pts: float, role: Role, eff: float) -> None:
        pts *= eff
        if p.bugs >= 1 and w.role in (Role.BACKEND, Role.FRONTEND, Role.DEVOPS, Role.INTERN):
            p.bugs -= min(p.bugs, pts * 0.075)
            pts *= 0.85
        risk = 0.010 * (1.6 - w.skill / 10.0) * (2.0 if self.crunch else 1.0)
        if w.energy < 25:
            risk *= 1.6
        if w.state is State.STRESSED:
            risk *= 1.5
        p.bugs += pts * risk
        sample = 40 + w.skill * 6 + (w.morale - 50) * 0.2 - (10 if self.crunch else 0)
        sample = max(0.0, min(100.0, sample))
        p.quality = (p.quality * p.done + sample * pts) / (p.done + pts) if p.done + pts > 0 else sample
        p.done += pts
        p.needs[role] -= pts
        w.xp += pts

    def _deliver(self, p: Project) -> None:
        self.projects.remove(p)
        pay = p.reward * (0.55 + 0.45 * p.quality / 100.0) - p.bugs * 60
        late = self.day > p.deadline_day
        if late:
            pay *= 0.6
        pay = int(max(300, pay))
        self.funds += pay
        self.income_today += pay
        self.delivered += 1
        self.celebrate_t = 5.0
        for w in self.workers:
            if w.state is not State.PANIC:
                w.start_celebrate()
        self.fx.append(("celebrate", None))
        self.fx.append(("money", f"+${pay:,}"))
        tag = " (GEÇ TESLİM -%40)" if late else ""
        self.announce(f"✨ '{p.name}' teslim edildi! +${pay:,}{tag}", C.GOLD)

    # ------------------------------------------------------------ aksiyonlar
    def new_candidates(self) -> None:
        self.candidates = []
        for _ in range(4):
            role = self.rng.choice(list(Role))
            skill = max(1, min(9, int(self.rng.gauss(5, 2)))) if role is not Role.INTERN else self.rng.randint(1, 3)
            self.candidates.append(Candidate(make_name(self.rng), role, skill, salary_for(role, skill),
                                             self.rng.choice(SKIN), self.rng.choice(HAIR)))

    def reroll_candidates(self):
        if self.funds < 150:
            return False, "Yetersiz bütçe ($150)."
        self.funds -= 150
        self.new_candidates()
        return True, "Yeni adaylar geldi (-$150)."

    def hire(self, index: int):
        if not 0 <= index < len(self.candidates):
            return False, "Geçersiz aday."
        if len(self.workers) >= MAX_WORKERS:
            return False, f"Ofis dolu (en fazla {MAX_WORKERS} çalışan)."
        c = self.candidates[index]
        if self.funds < c.fee:
            return False, f"Yetersiz bütçe (ücret ${c.fee:,})."
        self.funds -= c.fee
        self.candidates.pop(index)
        w = self._new_worker(c.name, c.role, c.skill, c.salary, c.skin, c.hair, at_entrance=True)
        self.say_log(f"{w.name} ({ROLE_INFO[w.role].short}) işe alındı.", C.GOOD)
        return True, f"{w.name} işe alındı (-${c.fee:,})."

    def fire(self, w: Worker):
        if w not in self.workers:
            return False, "Çalışan bulunamadı."
        if len(self.workers) <= 1:
            return False, "Son çalışanı kovamazsın!"
        sev = w.salary * 3
        if self.funds < sev:
            return False, f"Tazminat için bütçe yok (${sev:,})."
        self.funds -= sev
        self.workers.remove(w)
        for o in self.workers:
            o.morale = max(0.0, o.morale - 5)
        self.fx.append(("fired", w.name))
        self.say_log(f"{w.name} kovuldu (-${sev:,}). Ekip tedirgin.", C.BAD)
        return True, f"{w.name} kovuldu (-${sev:,})."

    def give_bonus(self, kind: str, w: Optional[Worker] = None):
        if kind == "one":
            if w is None or w not in self.workers:
                return False, "Çalışan seçili değil."
            cost = 300
            if self.funds < cost:
                return False, "Yetersiz bütçe."
            self.funds -= cost
            w.morale = min(100.0, w.morale + 35)
            w.say("PRİM!", 2.5)
            self.fx.append(("money", "-$300"))
            self.say_log(f"{w.name} prim aldı (+35 moral).", C.GOLD)
            return True, f"{w.name} prim aldı."
        cost = 150 * len(self.workers)
        if self.funds < cost:
            return False, f"Yetersiz bütçe (${cost:,})."
        self.funds -= cost
        for o in self.workers:
            o.morale = min(100.0, o.morale + 20)
            o.say("PRİM!", 2.0)
        self.say_log(f"Herkese prim dağıtıldı (-${cost:,}, +20 moral).", C.GOLD)
        return True, f"Tüm ekibe prim dağıtıldı (-${cost:,})."

    def order_snacks(self):
        cost = 120 + 15 * len(self.workers)
        if self.funds < cost:
            return False, f"Yetersiz bütçe (${cost:,})."
        self.funds -= cost
        for o in self.workers:
            o.energy = min(100.0, o.energy + 35)
            o.morale = min(100.0, o.morale + 5)
        self.fx.append(("snacks", None))
        self.say_log(f"☕ Premium kahve & atıştırmalık geldi (-${cost:,}).", C.COFFEE_COL)
        return True, f"Atıştırmalıklar geldi (-${cost:,})."

    def buy_upgrade(self, key: str):
        if key not in UPGRADES:
            return False, "Bilinmeyen yükseltme."
        name, cost, _ = UPGRADES[key]
        if key in self.upgrades:
            return False, "Zaten satın alındı."
        if self.funds < cost:
            return False, f"Yetersiz bütçe (${cost:,})."
        self.funds -= cost
        self.upgrades.add(key)
        self.office.apply_upgrade(key)
        self.say_log(f"Yükseltme alındı: {name}", C.ACCENT)
        return True, f"{name} kuruldu (-${cost:,})."

    def call_meeting(self):
        if self.meeting_t > 0:
            return False, "Toplantı zaten sürüyor."
        if self.meeting_cd > 0:
            return False, f"Toplantı için {int(self.meeting_cd)} sn bekle."
        self.meeting_t, self.meeting_cd = 9.0, 70.0
        self.say_log("Genel toplantı çağrıldı! Herkes masaya.", C.ACCENT)
        return True, "Genel toplantı başladı."

    def toggle_crunch(self):
        self.crunch = not self.crunch
        if self.crunch:
            self.say_log("🔥 CRUNCH TIME! İki kat hız, hızlı tükeniş.", C.BAD)
        else:
            self.say_log("Crunch bitti, nefes alın.", C.GOOD)
        return True, "Crunch " + ("AÇIK" if self.crunch else "kapalı")

    # ------------------------------------------------------------ olaylar
    def trigger_event(self, name: str) -> None:
        rng = self.rng
        if name in ("server", "prodbug"):
            if self.alert is not None:
                return
            self._alert_id += 1
            if name == "server":
                self.alert = Alert(self._alert_id, name, "SUNUCU ODASI AŞIRI ISINDI", 30, 35, 35)
                self.announce("🔥 Sunucu Odası Aşırı Isındı! Acil müdahale!", C.BAD)
            else:
                self.alert = Alert(self._alert_id, name, "PRODÜKSİYONDA KRİTİK HATA", 36, 40, 40)
                self.announce("📉 Prodüksiyonda Kritik Hata! Müşteriler şikayetçi!", C.BAD)
            self.fx.append(("alarm", name))
        elif name == "coffee":
            if self.coffee_broken > 0:
                return
            self.coffee_broken = 40.0
            for w in self.workers:
                w.morale = max(0.0, w.morale - 4)
                w.say("KAHVE YOK!", 2.5)
            self.announce("☕ Espresso Makinesi Bozuldu! Dev'ler paniğe kapıldı!", C.WARN)
        elif name == "donut":
            for w in self.workers:
                w.morale = min(100.0, w.morale + 15)
                w.say("Donut!", 2.0)
            self.fx.append(("donut", None))
            self.announce("🍩 Biri ofise donut getirdi! (+15 Moral)", C.GOOD)
        elif name == "innovation":
            self.innovation_t = 25.0
            for p in self.projects:
                p.quality = min(100.0, p.quality + 4)
            for w in self.workers:
                w.morale = min(100.0, w.morale + 6)
            self.fx.append(("bulb", None))
            self.announce("💡 Büyük İnovasyon Patlaması! 25 sn boyunca verim x1.5", C.GOLD)
        elif name == "client":
            amt = rng.randint(300, 900)
            self.funds += amt
            self.income_today += amt
            self.fx.append(("money", f"+${amt:,}"))
            self.announce(f"Memnun müşteri ekstra ödeme yaptı! +${amt:,}", C.GOOD)
        elif name == "flu":
            for w in rng.sample(self.workers, min(2, len(self.workers))):
                w.energy = max(0.0, w.energy - 30)
                w.morale = max(0.0, w.morale - 5)
                w.say("Hapşu!", 2.5)
            self.announce("Grip salgını! İki kişinin enerjisi düştü.", C.WARN)

    def _roll_event(self) -> None:
        pool = []
        for name, wt in EVENT_WEIGHTS:
            if name == "server" and "servers" in self.upgrades:
                wt *= 0.4
            if name in ("server", "prodbug") and self.alert is not None:
                continue
            if name == "coffee" and self.coffee_broken > 0:
                continue
            pool.append((name, wt))
        if not pool:
            return
        total = sum(w for _, w in pool)
        r = self.rng.uniform(0, total)
        for name, wt in pool:
            r -= wt
            if r <= 0:
                self.trigger_event(name)
                return

    def _update_alert(self, dt: float) -> None:
        a = self.alert
        if a is None:
            return
        fixers = [w for w in self.workers if w.state is State.PANIC and w.phase == "fix"]
        for w in fixers:
            a.progress += dt * (1.0 + w.skill * 0.08) * (2.0 if w.role.value == "devops" else 1.0)
        a.timer -= dt
        if a.progress >= a.need:
            for w in fixers:
                w.morale = min(100.0, w.morale + 8)
            self.announce("Kriz çözüldü! Ekip rahat bir nefes aldı.", C.GOOD)
            self.fx.append(("celebrate", None))
            self.alert = None
        elif a.timer <= 0:
            dmg = 900 if a.kind == "server" else 700
            self.funds -= dmg
            for w in self.workers:
                w.morale = max(0.0, w.morale - 8)
            for p in self.projects:
                p.bugs += 3
            self.fx.append(("money", f"-${dmg:,}"))
            self.announce(f"Kriz çözülemedi! Zarar -${dmg:,}, buglar arttı.", C.BAD)
            self.alert = None

    # ------------------------------------------------------------ gün sonu
    def end_day(self) -> None:
        salaries = sum(w.salary for w in self.workers)
        upkeep = RENT + 40 * len(self.upgrades)
        beans = 5 * len(self.workers) + 3 * self.cups_today
        retainer = min(400, 60 * self.delivered)
        self.funds += retainer - salaries - upkeep - beans
        if self.funds < 0:
            for w in self.workers:
                w.morale = max(0.0, w.morale - 8)
        self.last_report = (f"Gün {self.day}: gelir ${self.income_today + retainer:,} | "
                            f"gider ${salaries + upkeep + beans:,}")
        self.say_log("" + self.last_report, C.ACCENT)
        for p in list(self.projects):
            if self.day > p.deadline_day + 2:
                self.projects.remove(p)
                self.funds -= 1000
                for w in self.workers:
                    w.morale = max(0.0, w.morale - 10)
                self.announce(f"'{p.name}' iptal edildi (süre doldu, -$1,000).", C.BAD)
        self.day += 1
        self.tod = 0.0
        self.income_today = 0
        self.cups_today = 0
        self.new_candidates()
        if len(self.offers) < 3:
            self.new_offers()
        for w in self.workers:
            w.energy = min(100.0, w.energy + 25)

    # ------------------------------------------------------------ ana adım
    def update(self, dt: float) -> None:
        if self.game_over:
            return
        self.total_time += dt
        self.tod += dt
        if self.banner is not None:
            self.banner.ttl -= dt
            if self.banner.ttl <= 0:
                self.banner = None
        for attr in ("coffee_broken", "innovation_t", "meeting_cd", "celebrate_t"):
            v = getattr(self, attr)
            if v > 0:
                setattr(self, attr, max(0.0, v - dt))
        if self.meeting_t > 0:
            self.meeting_t -= dt
            if self.meeting_t <= 0:
                self.meeting_t = 0.0
                for p in self.projects:
                    p.quality = min(100.0, p.quality + 2)
                self.say_log("Toplantı bitti: herkes hizalandı (+2 kalite).", C.GOOD)
        self.event_t -= dt
        if self.event_t <= 0 and self.total_time > 15:
            self._roll_event()
            self.event_t = self.rng.uniform(18, 38)
        for w in list(self.workers):
            w.update(dt, self)
            pts = w.rate(self) * dt
            if pts > 0:
                if self.projects:
                    self._contribute(w, pts)
                elif self.total_time - self.idle_warn > 40:
                    self.idle_warn = self.total_time
                    self.say_log("Aktif sprint yok! [P] ile yeni proje başlat.", C.WARN)
            self._progress(w, dt)
        self._update_alert(dt)
        for p in list(self.projects):
            if p.remaining() <= 0.01:
                self._deliver(p)
        if self.tod >= DAY_LEN:
            self.end_day()
        if self.funds >= GOAL_FUNDS and not self.won:
            self.won = True
            self.announce(f"HEDEF: ${GOAL_FUNDS:,} bütçeye ulaştın! Oynamaya devam edebilirsin.", C.GOLD, 12)
        if self.funds <= BANKRUPT_AT:
            self.game_over = "Şirket iflas etti!"
        elif not self.workers:
            self.game_over = "Herkes istifa etti!"

    def _progress(self, w: Worker, dt: float) -> None:
        if w.morale < 5:
            w.quit_t += dt
            if w.quit_t > 25:
                self.workers.remove(w)
                self.announce(f"{w.name} tükenip istifa etti!", C.BAD)
                return
        else:
            w.quit_t = max(0.0, w.quit_t - dt)
        need = 150 + w.skill * 60
        if w.xp >= need and w.skill < 10:
            w.xp = 0
            w.skill += 1
            w.salary = int(w.salary * 1.08)
            w.say("Terfi!", 3.0)
            self.say_log(f"{w.name} seviye atladı (yetenek {w.skill}).", C.GOLD)
