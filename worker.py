"""Çalışanlar: roller, ihtiyaçlar, durum makinesi ve yürüme.

Simulation (ctx) şu arayüzü sağlar: office, rng, crunch, has(key), alert,
coffee_broken, innovation_t, meeting_t, workers, claim_spot(kind, worker),
nearby_chatters(worker), on_coffee(worker).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from colors import RGB

Pos = Tuple[int, int]


class Role(Enum):
    BACKEND = "backend"
    FRONTEND = "frontend"
    UIUX = "uiux"
    DEVOPS = "devops"
    MARKETING = "marketing"
    INTERN = "intern"


@dataclass(frozen=True)
class RoleInfo:
    title: str
    short: str
    color: RGB
    base_salary: int
    activity: str


ROLE_INFO = {
    Role.BACKEND: RoleInfo("Backend Developer", "BE", (80, 140, 255), 190, "API yazıyor"),
    Role.FRONTEND: RoleInfo("Frontend Developer", "FE", (255, 140, 70), 180, "Component çiziyor"),
    Role.UIUX: RoleInfo("UI/UX Designer", "UX", (230, 100, 200), 170, "Figma'da tasarlıyor"),
    Role.DEVOPS: RoleInfo("DevOps Engineer", "DO", (70, 200, 140), 200, "Pipeline kuruyor"),
    Role.MARKETING: RoleInfo("Marketing Specialist", "MK", (250, 210, 70), 150, "Kampanya planlıyor"),
    Role.INTERN: RoleInfo("Intern (Stajyer)", "IN", (170, 172, 188), 60, "Testleri koşturuyor"),
}


class State(Enum):
    WORKING = "WORKING"
    COFFEE_RUN = "COFFEE_RUN"
    WATER_COOLER_CHAT = "WATER_COOLER_CHAT"
    STRESSED = "STRESSED"
    SLEEPING = "SLEEPING"
    PANIC = "PANIC"
    CELEBRATING = "CELEBRATING"
    LOUNGE = "LOUNGE"
    MEETING = "MEETING"


# kısa kod, renk, açıklama
STATE_INFO = {
    State.WORKING: ("KOD", (90, 200, 255), "Çalışıyor"),
    State.COFFEE_RUN: ("KHV", (210, 150, 90), "Kahve molasında"),
    State.WATER_COOLER_CHAT: ("SOH", (140, 220, 255), "Su sebilinde sohbet"),
    State.STRESSED: ("STR", (255, 130, 90), "Tükenmiş (burnout)"),
    State.SLEEPING: ("UYK", (150, 160, 255), "Masada uyukluyor"),
    State.PANIC: ("PNK", (255, 70, 70), "Panikte!"),
    State.CELEBRATING: ("KUT", (255, 220, 90), "Kutluyor"),
    State.LOUNGE: ("DNL", (120, 220, 180), "Dinleniyor"),
    State.MEETING: ("TOP", (200, 170, 255), "Toplantıda"),
}

PANIC_P = {Role.DEVOPS: 1.0, Role.BACKEND: 0.85, Role.INTERN: 0.8,
           Role.FRONTEND: 0.4, Role.UIUX: 0.3, Role.MARKETING: 0.3}

FIRST = ["Ayşe", "Mehmet", "Elif", "Can", "Zeynep", "Burak", "Selin", "Emre", "Deniz", "Cem",
         "Merve", "Kaan", "Ceren", "Onur", "Gizem", "Barış", "Pelin", "Tolga", "Defne", "Ege",
         "Ece", "Arda", "Naz", "Yiğit", "İrem", "Mert", "Şeyma", "Umut", "Buse", "Oğuz"]
LAST = ["Yılmaz", "Kaya", "Demir", "Çelik", "Şahin", "Arslan", "Koç", "Aydın", "Özdemir", "Polat",
        "Erdoğan", "Güneş", "Aksoy", "Korkmaz", "Tekin", "Yıldız", "Bulut", "Kurt", "Işık", "Sezer"]
SKIN = [(255, 224, 189), (241, 194, 125), (224, 172, 105), (198, 134, 66), (141, 85, 36)]
HAIR = [(40, 28, 20), (92, 60, 36), (190, 140, 70), (220, 220, 225), (150, 40, 30), (20, 20, 24), (120, 70, 160)]
CHAT_LINES = ["Kahve?", "Dün maç!", "LGTM!", "Standup...", "Prod yine!", "Pazartesi", "Merge?",
              "Hafta sonu?", "Donut var mı", "Sprint ağır", "Zam yok mu?", "Hot-fix!", "Regex tövbe"]


def make_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def salary_for(role: Role, skill: int) -> int:
    return int(ROLE_INFO[role].base_salary * (0.7 + skill * 0.12))


@dataclass(eq=False)
class Worker:
    wid: int
    name: str
    role: Role
    skill: int
    salary: int
    seat: Pos
    skin: RGB = (241, 194, 125)
    hair: RGB = (40, 28, 20)
    morale: float = 75.0
    energy: float = 90.0
    state: State = State.WORKING
    pos: Pos = (0, 0)
    prev: Pos = (0, 0)
    move_t: float = 1.0
    path: List[Pos] = field(default_factory=list)
    target: Optional[Pos] = None
    phase: str = ""
    timer: float = 0.0
    decide_t: float = 1.0
    social: float = 0.0
    social_limit: float = 70.0
    cup_t: float = 0.0
    age: float = 0.0
    moving: bool = False
    seen_alert: int = 0
    xp: float = 0.0
    quit_t: float = 0.0
    bubble: str = ""
    bubble_t: float = 0.0
    chat_t: float = 0.0

    def __post_init__(self) -> None:
        if self.pos == (0, 0):
            self.pos = self.seat
        self.prev = self.pos

    # ------------------------------------------------------------ özellikler
    @property
    def px(self) -> float:
        f = min(1.0, self.move_t)
        return self.prev[0] + (self.pos[0] - self.prev[0]) * f

    @property
    def py(self) -> float:
        f = min(1.0, self.move_t)
        return self.prev[1] + (self.pos[1] - self.prev[1]) * f

    @property
    def seated(self) -> bool:
        return self.pos == self.seat and not self.path and self.move_t >= 1.0

    @property
    def producing(self) -> bool:
        return self.state in (State.WORKING, State.STRESSED) and self.seated

    def activity(self) -> str:
        if self.state is State.WORKING:
            return ROLE_INFO[self.role].activity if self.seated else "Masasına yürüyor"
        return STATE_INFO[self.state][2]

    def say(self, text: str, secs: float = 2.0) -> None:
        self.bubble, self.bubble_t = text, secs

    # ------------------------------------------------------------ verim
    def rate(self, ctx) -> float:
        """Saniyedeki iş puanı (yalnızca masada çalışırken)."""
        if not self.producing:
            return 0.0
        base = 0.20 + self.skill * 0.06
        m = base * (0.6 + 0.4 * self.morale / 100.0) * (0.5 + 0.5 * min(1.0, self.energy / 40.0))
        if self.state is State.STRESSED:
            m *= 0.2
        if ctx.crunch:
            m *= 2.0
        if ctx.has("monitors"):
            m *= 1.2
        if ctx.innovation_t > 0:
            m *= 1.5
        return m

    def rate_estimate(self) -> float:
        return (0.20 + self.skill * 0.06) * 0.85

    # ------------------------------------------------------------ hareket
    def goto(self, dest: Pos, ctx) -> bool:
        path = ctx.office.find_path(self.pos, dest)
        if path is None:
            return False
        self.path = path
        return True

    def _walk(self, dt: float, step: float) -> bool:
        if self.move_t < 1.0:
            self.move_t += dt / step
            if self.move_t < 1.0:
                return True
            self.move_t = 1.0
        if self.path:
            self.prev = self.pos
            self.pos = self.path.pop(0)
            self.move_t = 0.0
            return True
        return False

    # ------------------------------------------------------------ durum geçişleri
    def _finish(self) -> None:
        self.state = State.WORKING
        self.target = None
        self.phase = ""
        self.path = []

    def _start_trip(self, state: State, kind: str, ctx) -> bool:
        spot = ctx.claim_spot(kind, self)
        if spot is None or not self.goto(spot, ctx):
            return False
        self.state, self.target, self.phase = state, spot, "walk"
        return True

    def start_celebrate(self, secs: float = 4.5) -> None:
        self.state, self.phase, self.timer = State.CELEBRATING, "act", secs
        self.path = []
        self.target = None
        self.say("YEEE!", 2.0)

    def _enter_panic(self, ctx, alert_id: int) -> None:
        if self._start_trip(State.PANIC, "server", ctx):
            self.say("SUNUCU!", 2.0)
            self.timer = alert_id

    # ------------------------------------------------------------ ana döngü
    def update(self, dt: float, ctx) -> None:
        self.age += dt
        if self.bubble_t > 0:
            self.bubble_t -= dt
        if self.cup_t > 0:
            self.cup_t -= dt
        self._drift(dt, ctx)
        self._interrupts(ctx)
        step = 0.15 if self.state is State.PANIC else (0.24 if ctx.crunch else 0.30)
        self.moving = self._walk(dt, step)
        if self.moving:
            return
        getattr(self, "_do_" + self.state.value.lower())(dt, ctx)

    def _drift(self, dt: float, ctx) -> None:
        e, m = 0.0, 0.0
        if self.producing:
            crunch = 2.3 if ctx.crunch else 1.0
            e = -0.5 * crunch * (0.75 if ctx.has("chairs") else 1.0) * (0.7 if self.cup_t > 0 else 1.0)
            m = -0.09 * (2.5 if ctx.crunch else 1.0)
            if self.state is State.STRESSED:
                m += 0.18
            if ctx.has("arcade"):
                m += 0.03
            if not ctx.crunch:
                self.social += dt * ctx.rng.uniform(0.8, 1.2)
        elif self.state is State.PANIC:
            e, m = -0.8, -0.6
        elif self.moving:
            e = -0.15
        if self.energy < 15:
            m -= 0.2
        self.energy = max(0.0, min(100.0, self.energy + e * dt))
        self.morale = max(0.0, min(100.0, self.morale + m * dt))

    def _interrupts(self, ctx) -> None:
        a = ctx.alert
        if a is not None and a.id != self.seen_alert:
            self.seen_alert = a.id
            if self.state is not State.CELEBRATING and ctx.rng.random() < PANIC_P[self.role]:
                self._enter_panic(ctx, a.id)
                return
        if ctx.meeting_t > 0 and self.state not in (State.MEETING, State.PANIC, State.CELEBRATING):
            if self._start_trip(State.MEETING, "meeting", ctx):
                self.say("Toplantı...", 2.0)

    # ------------------------------------------------------------ durum işleyicileri
    def _go_to_seat(self, ctx) -> bool:
        if self.pos == self.seat:
            return False
        if not self.goto(self.seat, ctx):
            self.pos = self.prev = self.seat
        return True

    def _do_working(self, dt: float, ctx) -> None:
        if self._go_to_seat(ctx):
            return
        self.decide_t -= dt
        if self.decide_t > 0:
            return
        rng = ctx.rng
        self.decide_t = 0.8 + rng.random()
        if self.state is State.WORKING and self.morale < 22:
            self.state = State.STRESSED
            self.say("Yeter artık!", 2.5)
        elif self.state is State.STRESSED and self.morale >= 40:
            self.state = State.WORKING
            self.say("Toparladım", 2.0)
        if self.energy < 9:
            self.state, self.phase = State.SLEEPING, "act"
            return
        if self.energy < 34 and rng.random() < 0.5:
            if self.energy < 24 and rng.random() < 0.4:
                if self._start_trip(State.LOUNGE, "lounge", ctx):
                    return
            if self._start_trip(State.COFFEE_RUN, "coffee", ctx):
                self.say("Kahve lazım", 2.0)
                return
        if self.state is State.WORKING and self.social > self.social_limit and self.energy > 30:
            self.social = 0.0
            self.social_limit = rng.uniform(45, 110)
            self._start_trip(State.WATER_COOLER_CHAT, "cooler", ctx)

    _do_stressed = _do_working

    def _do_sleeping(self, dt: float, ctx) -> None:
        self.energy = min(100.0, self.energy + 2.4 * dt)
        if self.energy >= 55:
            self.state = State.WORKING
            self.say("Uyumadım!", 2.0)

    def _do_coffee_run(self, dt: float, ctx) -> None:
        if self.phase == "walk":
            self.phase, self.timer = "act", (1.2 if ctx.has("coffee_bar") else 2.2)
            return
        self.timer -= dt
        if self.timer > 0:
            return
        if ctx.coffee_broken > 0:
            self.morale = max(0.0, self.morale - 6)
            self.say("ARIZALI!!", 2.5)
        else:
            self.energy = min(100.0, self.energy + (50 if ctx.has("coffee_bar") else 36))
            self.morale = min(100.0, self.morale + 2)
            self.cup_t = 10.0
            ctx.on_coffee(self)
        self._finish()

    def _do_water_cooler_chat(self, dt: float, ctx) -> None:
        if self.phase == "walk":
            self.phase, self.timer = "act", ctx.rng.uniform(6, 10)
            return
        self.timer -= dt
        buddies = ctx.nearby_chatters(self)
        self.morale = min(100.0, self.morale + dt * (1.0 if buddies else 0.25))
        self.chat_t -= dt
        if self.chat_t <= 0:
            self.chat_t = 2.4
            self.say(ctx.rng.choice(CHAT_LINES), 2.2)
        if self.timer <= 0:
            self.energy = min(100.0, self.energy + 4)
            self._finish()

    def _do_lounge(self, dt: float, ctx) -> None:
        if self.phase == "walk":
            self.phase, self.timer = "act", ctx.rng.uniform(8, 11)
            return
        self.timer -= dt
        self.energy = min(100.0, self.energy + 4.2 * dt)
        self.morale = min(100.0, self.morale + (3.0 if ctx.has("arcade") else 1.0) * dt)
        if ctx.has("arcade") and ctx.rng.random() < dt * 0.3:
            self.say("GOL!", 1.5)
        if self.timer <= 0:
            self._finish()

    def _do_panic(self, dt: float, ctx) -> None:
        if self.phase == "walk":
            self.phase = "fix"
            return
        a = ctx.alert
        if a is None or a.id != int(self.timer):
            self.say("Oh be!", 2.0)
            self._finish()

    def _do_celebrating(self, dt: float, ctx) -> None:
        self.timer -= dt
        self.morale = min(100.0, self.morale + 2.0 * dt)
        if self.timer <= 0:
            self._finish()

    def _do_meeting(self, dt: float, ctx) -> None:
        if self.phase == "walk":
            self.phase = "act"
            return
        self.morale = min(100.0, self.morale + 1.5 * dt)
        if ctx.meeting_t <= 0:
            self._finish()
