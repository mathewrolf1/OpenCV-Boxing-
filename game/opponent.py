"""
AI opponent: state machine with tells, attacks, vulnerability windows.
States: idle | telegraph | attacking | vulnerable | blocking
"""

import os
import random
from PIL import Image
from game.constants import (
    OPPONENT_MAX_HP,
    TELEGRAPH_DURATION,
    VULNERABLE_DURATION,
    PUNCH_LEFT,
    PUNCH_RIGHT,
)


class Opponent:
    def __init__(self):
        self.hp = OPPONENT_MAX_HP
        self.max_hp = OPPONENT_MAX_HP
        self.state = "idle"
        self.state_timer = 0.0
        self.attack_side = None  # PUNCH_LEFT | PUNCH_RIGHT
        self.combo_index = 0
        self.round = 1
        self.hit_timer = 0.0
        self.invuln_timer = 0.0
        self.hit_anim_duration = _load_hit_anim_duration()

    def reset(self, round_num: int = 1):
        self.hp = self.max_hp
        self.state = "idle"
        self.state_timer = 0.0
        self.attack_side = None
        self.combo_index = 0
        self.round = round_num
        self.hit_timer = 0.0
        self.invuln_timer = 0.0
        self.hit_anim_duration = _load_hit_anim_duration()

    def _telegraph_duration(self) -> float:
        """Shorter telegraph in later rounds."""
        return max(0.2, TELEGRAPH_DURATION - (self.round - 1) * 0.05)

    def _choose_next_attack(self) -> str:
        """Simple pattern: jab, jab, cross with occasional block."""
        r = random.random()
        if r < 0.15:
            return "block"
        if self.combo_index == 0 or self.combo_index == 1:
            return random.choice([PUNCH_LEFT, PUNCH_RIGHT])
        return random.choice([PUNCH_LEFT, PUNCH_RIGHT])  # cross

    def update(self, dt: float) -> dict | None:
        """
        Update AI. Returns attack info when attacking: {"side": "left"|"right", "damage": float}
        or None.
        """
        self.state_timer -= dt
        self.hit_timer = max(0, self.hit_timer - dt)
        self.invuln_timer = max(0, self.invuln_timer - dt)
        if self.hit_timer > 0:
            return None
        attack_result = None

        if self.state == "idle":
            if self.state_timer <= 0:
                action = self._choose_next_attack()
                if action == "block":
                    self.state = "blocking"
                    self.state_timer = random.uniform(0.5, 1.2)
                else:
                    self.state = "telegraph"
                    self.attack_side = action
                    self.state_timer = self._telegraph_duration()

        elif self.state == "telegraph":
            if self.state_timer <= 0:
                self.state = "attacking"
                self.state_timer = 0.15  # attack duration
                attack_result = {"side": self.attack_side, "damage": 1}

        elif self.state == "attacking":
            if self.state_timer <= 0:
                self.state = "vulnerable"
                self.state_timer = VULNERABLE_DURATION
                self.combo_index = (self.combo_index + 1) % 3

        elif self.state == "vulnerable":
            if self.state_timer <= 0:
                self.state = "idle"
                self.state_timer = random.uniform(0.2, 0.5)  # Shorter idle = more punch opportunities

        elif self.state == "blocking":
            if self.state_timer <= 0:
                self.state = "idle"
                self.state_timer = random.uniform(0.2, 0.5)

        return attack_result

    def take_damage(self, amount: float) -> bool:
        """Apply damage when vulnerable. Returns True if damage was taken."""
        if self.state != "vulnerable" or self.invuln_timer > 0:
            return False
        self.hp = max(0, self.hp - amount)
        self.hit_timer = self.hit_anim_duration
        self.invuln_timer = self.hit_timer
        return True

    @property
    def is_vulnerable(self) -> bool:
        return self.state == "vulnerable"

    @property
    def is_alive(self) -> bool:
        return self.hp > 0


def _load_hit_anim_duration() -> float:
    """Compute total hit animation duration (seconds) from GIF frames."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "assets", "brandon_enemy", "brandonhit.gif")
    try:
        total_ms = 0
        with Image.open(path) as im:
            for i in range(im.n_frames):
                im.seek(i)
                total_ms += im.info.get("duration", 100)
        return max(0.1, total_ms / 1000.0)
    except Exception:
        return 0.6

