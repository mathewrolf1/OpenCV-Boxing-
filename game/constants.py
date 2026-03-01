"""Game constants: screen size, timings, punch types."""

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
TITLE = "Punch Out - CV Boxing"

# Punch types
PUNCH_LEFT = "left"
PUNCH_RIGHT = "right"

# Round / timing
ROUND_DURATION = 90  # seconds
ROUNDS_TOTAL = 3
TELEGRAPH_DURATION = 0.4
VULNERABLE_DURATION = 1.0  # Longer window for players to land punches
PUNCH_COOLDOWN = 0.2
BLOCK_SUSTAIN_SEC = 0.12  # hysteresis: keep block active briefly after CV drops
BLOCK_COOLDOWN_AFTER_HIT = 0.7  # seconds block disabled after successfully blocking

# HP
PLAYER_MAX_HP = 12
OPPONENT_MAX_HP = 6
