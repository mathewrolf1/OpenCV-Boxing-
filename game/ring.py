"""
Ring rendering: opponent, HUD, Punch Out aesthetic.
First-person view with opponent in center.
"""

import os
import time
import math
import pygame
from PIL import Image
from game.constants import ROUND_DURATION

# Background image (loaded once)
_BG_IMAGE = None

# QR code image (loaded once)
_QR_IMAGE = None

# Enemy animations loaded once: state -> list[(surface, duration_ms)]
_ENEMY_ANIMS = None
_ENEMY_ANIM_STATE = {"state": None, "frame": 0, "last_time": 0.0}


def _load_background():
    global _BG_IMAGE
    if _BG_IMAGE is not None:
        return _BG_IMAGE
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "assets", "background.png")
    try:
        _BG_IMAGE = pygame.image.load(path).convert()
    except pygame.error:
        _BG_IMAGE = None
    return _BG_IMAGE


def _load_qr():
    global _QR_IMAGE
    if _QR_IMAGE is not None:
        return _QR_IMAGE
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "assets", "qrcode.png")
    try:
        _QR_IMAGE = pygame.image.load(path).convert_alpha()
    except pygame.error:
        _QR_IMAGE = None
    return _QR_IMAGE


def _load_enemy_anims():
    """
    Load opponent animations from assets/brandon_enemy/*.gif
    Returns dict: state -> list of (surface, duration_ms)
    """
    global _ENEMY_ANIMS
    if _ENEMY_ANIMS is not None:
        return _ENEMY_ANIMS

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    anim_dir = os.path.join(base, "assets", "brandon_enemy")
    files = {
        "idle": "brandonidle.gif",
        "telegraph": "brandonwind.gif",
        "attacking": "brandonpunch.gif",
        "vulnerable": "brandonvunerable.gif",
        "blocking": "brandonhit.gif",  # using hit gif for guard
        "hit": "brandonhit.gif",
    }

    anims = {}
    for state, fname in files.items():
        path = os.path.join(anim_dir, fname)
        frames = []
        try:
            with Image.open(path) as im:
                for i in range(im.n_frames):
                    im.seek(i)
                    duration = im.info.get("duration", 100)  # ms
                    rgba = im.convert("RGBA")
                    mode = rgba.mode
                    size = rgba.size
                    data = rgba.tobytes()
                    surf = pygame.image.fromstring(data, size, mode).convert_alpha()
                    frames.append((surf, duration))
        except Exception:
            frames = []
        if frames:
            anims[state] = frames
    _ENEMY_ANIMS = anims
    return _ENEMY_ANIMS
from game.player import Player
from game.opponent import Opponent
from game.states import TITLE, FIGHTING, ROUND_END, GAME_OVER, VICTORY, CALIBRATION


# NES-style palette (Pygame uses 0-255)
COLOR_BG = (30, 26, 38)
COLOR_RING = (64, 56, 77)
COLOR_RING_LINE = (128, 115, 153)
COLOR_PLAYER_HP = (51, 153, 242)
COLOR_OPPONENT_HP = (230, 64, 51)
COLOR_TEXT = (255, 255, 255)
COLOR_ACCENT = (255, 230, 77)


def draw_hud(surface: pygame.Surface, player: Player, opponent: Opponent, round_num: int, round_time: float):
    """Draw HP bars and round timer."""
    sw, sh = surface.get_width(), surface.get_height()
    bar_w = 200
    bar_h = 20
    x, y = 20, sh - 40
    pygame.draw.rect(surface, (51, 51, 64), (x, y, bar_w, bar_h))
    fill_w = max(0, int(bar_w * player.hp / player.max_hp))
    pygame.draw.rect(surface, COLOR_PLAYER_HP, (x, y, fill_w, bar_h))
    pygame.draw.rect(surface, COLOR_RING_LINE, (x, y, bar_w, bar_h), 2)
    font = pygame.font.Font(None, 24)
    surface.blit(font.render("YOU", True, COLOR_TEXT), (x, y - 18))
    # Segment lines for player HP (4 hits)
    if player.max_hp > 0:
        for i in range(1, player.max_hp):
            sx = x + int(bar_w * (i / player.max_hp))
            pygame.draw.line(surface, (0, 0, 0), (sx, y), (sx, y + bar_h), 3)
    if player.blocking:
        block_label = font.render("BLOCK", True, (0, 255, 120))
        surface.blit(block_label, (x + bar_w + 12, y + 2))

    # Opponent HP (top)
    x2 = sw - 20 - bar_w
    y2 = 20
    pygame.draw.rect(surface, (51, 51, 64), (x2, y2, bar_w, bar_h))
    fill_w2 = max(0, int(bar_w * opponent.hp / opponent.max_hp))
    pygame.draw.rect(surface, COLOR_OPPONENT_HP, (x2, y2, fill_w2, bar_h))
    pygame.draw.rect(surface, COLOR_RING_LINE, (x2, y2, bar_w, bar_h), 2)
    surface.blit(font.render("OPPONENT", True, COLOR_TEXT), (x2, y2 - 18))
    # Segment lines for opponent HP (6 hits)
    if opponent.max_hp > 0:
        for i in range(1, opponent.max_hp):
            sx = x2 + int(bar_w * (i / opponent.max_hp))
            pygame.draw.line(surface, (0, 0, 0), (sx, y2), (sx, y2 + bar_h), 3)

    # Round timer
    remaining = max(0, ROUND_DURATION - round_time)
    timer_text = f"{int(remaining // 60):02}:{int(remaining % 60):02}"
    timer_surf = font.render(timer_text, True, COLOR_ACCENT)
    surface.blit(timer_surf, (sw // 2 - timer_surf.get_width() // 2, 20))


def _get_enemy_frame(state: str) -> pygame.Surface | None:
    """Return current frame surface for the given state, advancing animation."""
    anims = _load_enemy_anims()
    frames = anims.get(state) or anims.get("idle")
    if not frames:
        return None
    now = time.monotonic()
    if _ENEMY_ANIM_STATE["state"] != state:
        _ENEMY_ANIM_STATE["state"] = state
        _ENEMY_ANIM_STATE["frame"] = 0
        _ENEMY_ANIM_STATE["last_time"] = now
    frame_idx = _ENEMY_ANIM_STATE["frame"]
    elapsed = (now - _ENEMY_ANIM_STATE["last_time"]) * 1000.0  # ms
    while elapsed > frames[frame_idx][1]:
        elapsed -= frames[frame_idx][1]
        frame_idx = (frame_idx + 1) % len(frames)
        _ENEMY_ANIM_STATE["last_time"] = now - (elapsed / 1000.0)
    _ENEMY_ANIM_STATE["frame"] = frame_idx
    return frames[frame_idx][0]


def draw_opponent(surface: pygame.Surface, opponent: Opponent):
    """Draw opponent using GIF animations. Positioned in upper third."""
    sw, sh = surface.get_width(), surface.get_height()
    cx = sw // 2
    cy = int(sh * 0.42)
    w, h = 384, 432  # render size (20% bigger)

    anim_state = "hit" if opponent.hit_timer > 0 else opponent.state
    frame = _get_enemy_frame(anim_state)
    if frame:
        sprite = pygame.transform.smoothscale(frame, (w, h))
        rect = sprite.get_rect(center=(cx, cy))
        surface.blit(sprite, rect)
        # State box color (green when hittable); hide during hit animation
        if anim_state != "hit":
            box_color = COLOR_RING_LINE
            if opponent.state == "telegraph":
                box_color = (153, 77, 77)  # red wind-up
            elif opponent.state == "vulnerable":
                box_color = (89, 200, 120)  # green hittable
            elif opponent.state == "blocking":
                box_color = (89, 89, 200)  # blue guard
            pygame.draw.rect(surface, box_color, rect.inflate(12, 12), 4)
    else:
        # Fallback: simple shapes
        rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
        color = (102, 89, 115)
        if opponent.state == "telegraph":
            color = (153, 77, 77)
        elif opponent.state == "vulnerable":
            color = (89, 128, 102)
        elif opponent.state == "blocking":
            color = (89, 89, 128)
        pygame.draw.rect(surface, color, rect)
        pygame.draw.rect(surface, COLOR_RING_LINE, rect, 4)


def draw_ring(surface: pygame.Surface):
    """Draw the boxing ring background."""
    sw, sh = surface.get_width(), surface.get_height()
    margin = 40
    ring_rect = pygame.Rect(margin, margin, sw - 2 * margin, sh - 2 * margin)
    bg = _load_background()
    if bg is not None:
        scaled = pygame.transform.smoothscale(bg, (ring_rect.width, ring_rect.height))
        surface.blit(scaled, (ring_rect.x, ring_rect.y))
    else:
        pygame.draw.rect(surface, COLOR_RING, ring_rect)
    pygame.draw.rect(surface, COLOR_RING_LINE, ring_rect, 6)


def draw_title(surface: pygame.Surface):
    """Draw title screen."""
    sw, sh = surface.get_width(), surface.get_height()
    font_large = pygame.font.Font(None, 72)
    font_small = pygame.font.Font(None, 32)
    title = font_large.render("FIGHT BRANDON", True, COLOR_ACCENT)
    sub = font_small.render("Press SPACE to fight", True, COLOR_TEXT)
    hint = font_small.render("Punch toward the camera to attack", True, (179, 179, 191))
    fullscreen_hint = font_small.render("Press F for fullscreen", True, (150, 150, 160))
    title_x = sw // 2 - title.get_width() // 2
    title_y = 180
    bg_padding = 12
    bg_rect = pygame.Rect(
        title_x - bg_padding,
        title_y - bg_padding,
        title.get_width() + bg_padding * 2,
        title.get_height() + bg_padding * 2,
    )
    pygame.draw.rect(surface, (20, 20, 28), bg_rect)
    pygame.draw.rect(surface, COLOR_RING_LINE, bg_rect, 3)
    surface.blit(title, (title_x, title_y))
    surface.blit(sub, (sw // 2 - sub.get_width() // 2, 300))
    surface.blit(hint, (sw // 2 - hint.get_width() // 2, 350))
    surface.blit(fullscreen_hint, (sw // 2 - fullscreen_hint.get_width() // 2, 390))


def draw_round_end(surface: pygame.Surface, round_num: int, player_won: bool):
    """Draw round end screen."""
    sw = surface.get_width()
    font = pygame.font.Font(None, 48)
    if player_won:
        text = f"Round {round_num} - You won!"
    else:
        text = f"Round {round_num} - Opponent won"
    surf = font.render(text, True, COLOR_ACCENT)
    surface.blit(surf, (sw // 2 - surf.get_width() // 2, 250))
    sub = pygame.font.Font(None, 28).render("Press SPACE to continue", True, COLOR_TEXT)
    surface.blit(sub, (sw // 2 - sub.get_width() // 2, 320))


def draw_game_over(surface: pygame.Surface):
    """Draw game over / KO screen."""
    sw = surface.get_width()
    font = pygame.font.Font(None, 64)
    text = font.render("KNOCKOUT!", True, (242, 51, 51))
    surface.blit(text, (sw // 2 - text.get_width() // 2, 220))
    sub = pygame.font.Font(None, 32).render("Press R to restart", True, COLOR_TEXT)
    surface.blit(sub, (sw // 2 - sub.get_width() // 2, 300))
    # QR code (centered, big)
    qr = _load_qr()
    if qr:
        size = int(min(surface.get_width(), surface.get_height()) * 0.45)
        qr_surf = pygame.transform.smoothscale(qr, (size, size))
        rect = qr_surf.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2 + 40))
        surface.blit(qr_surf, rect)
        join = pygame.font.Font(None, 40).render("JOIN FLC++", True, COLOR_TEXT)
        surface.blit(join, (rect.centerx - join.get_width() // 2, rect.bottom + 10))


def draw_victory(surface: pygame.Surface):
    """Draw victory screen."""
    sw = surface.get_width()
    font = pygame.font.Font(None, 64)
    text = font.render("VICTORY!", True, COLOR_ACCENT)
    surface.blit(text, (sw // 2 - text.get_width() // 2, 220))
    sub = pygame.font.Font(None, 32).render("Press R to play again", True, COLOR_TEXT)
    surface.blit(sub, (sw // 2 - sub.get_width() // 2, 300))
    # QR code (centered, big)
    qr = _load_qr()
    if qr:
        size = int(min(surface.get_width(), surface.get_height()) * 0.45)
        qr_surf = pygame.transform.smoothscale(qr, (size, size))
        rect = qr_surf.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2 + 40))
        surface.blit(qr_surf, rect)
        join = pygame.font.Font(None, 40).render("JOIN FLC++", True, COLOR_TEXT)
        surface.blit(join, (rect.centerx - join.get_width() // 2, rect.bottom + 10))


def draw_countdown(surface: pygame.Surface, seconds_left: float):
    """Draw a full-screen countdown before the fight."""
    sw, sh = surface.get_width(), surface.get_height()
    overlay = pygame.Surface((sw, sh))
    overlay.set_alpha(220)
    overlay.fill((0, 0, 0))
    surface.blit(overlay, (0, 0))
    num = int(math.ceil(seconds_left))
    font = pygame.font.Font(None, 140)
    if num <= 0:
        text = font.render("FIGHT!", True, COLOR_ACCENT)
    else:
        text = font.render(str(num), True, COLOR_ACCENT)
    surface.blit(text, (sw // 2 - text.get_width() // 2, sh // 2 - text.get_height() // 2))


def render(surface: pygame.Surface, state: str, player: Player, opponent: Opponent,
           round_num: int, round_time: float, round_end_player_won: bool | None = None,
           countdown_seconds: float | None = None):
    """Main render entry: dispatches to appropriate draw based on state."""
    surface.fill(COLOR_BG)

    if state == TITLE:
        draw_ring(surface)
        draw_title(surface)
        return

    if state == CALIBRATION:
        draw_ring(surface)
        draw_countdown(surface, countdown_seconds or 0)
        return

    if state == FIGHTING:
        draw_ring(surface)
        draw_opponent(surface, opponent)
        draw_hud(surface, player, opponent, round_num, round_time)
        if opponent.hit_timer > 0:
            sw, sh = surface.get_width(), surface.get_height()
            font = pygame.font.Font(None, 96)
            hit_text = font.render("HIT", True, (255, 230, 77))
            surface.blit(hit_text, (sw // 2 - hit_text.get_width() // 2, sh * 0.08))
        return

    if state == ROUND_END:
        draw_ring(surface)
        draw_opponent(surface, opponent)
        draw_hud(surface, player, opponent, round_num, round_time)
        sw, sh = surface.get_width(), surface.get_height()
        overlay = pygame.Surface((sw, sh))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        surface.blit(overlay, (0, 0))
        draw_round_end(surface, round_num, round_end_player_won or False)
        return

    if state == GAME_OVER:
        draw_ring(surface)
        sw, sh = surface.get_width(), surface.get_height()
        overlay = pygame.Surface((sw, sh))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        surface.blit(overlay, (0, 0))
        draw_game_over(surface)
        return

    if state == VICTORY:
        draw_ring(surface)
        sw, sh = surface.get_width(), surface.get_height()
        overlay = pygame.Surface((sw, sh))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        surface.blit(overlay, (0, 0))
        draw_victory(surface)
        return
