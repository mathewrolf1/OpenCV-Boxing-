"""Player state: HP, dodging, blocking."""

from game.constants import PLAYER_MAX_HP


class Player:
    def __init__(self):
        self.hp = PLAYER_MAX_HP
        self.max_hp = PLAYER_MAX_HP
        self.dodging = None  # "left" | "right" | None
        self.blocking = False
        self.invincibility_timer = 0.0
        self.invincibility_duration = 0.5
        self.block_cooldown_timer = 0.0  # block disabled after successfully blocking a hit

    def reset(self):
        self.hp = self.max_hp
        self.dodging = None
        self.blocking = False
        self.invincibility_timer = 0.0
        self.block_cooldown_timer = 0.0

    def take_damage(self, amount: float) -> bool:
        """Apply damage if not invincible. Returns True if damage was taken."""
        if self.invincibility_timer > 0:
            return False
        self.hp = max(0, self.hp - amount)
        self.invincibility_timer = self.invincibility_duration
        return True

    def update(self, dt: float):
        self.invincibility_timer = max(0, self.invincibility_timer - dt)
        self.block_cooldown_timer = max(0, self.block_cooldown_timer - dt)

    @property
    def is_alive(self) -> bool:
        return self.hp > 0
