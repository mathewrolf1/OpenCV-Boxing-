"""
Punch Out-style boxing game with webcam punch detection.
Entry point: spawns CV thread + Pygame game loop.
"""
import queue
import threading
import numpy as np
import pygame
import cv2
from game.constants import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    TITLE,
    ROUND_DURATION,
    ROUNDS_TOTAL,
    PUNCH_LEFT,
    PUNCH_RIGHT,
    BLOCK_SUSTAIN_SEC,
    BLOCK_COOLDOWN_AFTER_HIT,
)
from game.player import Player
from game.opponent import Opponent
from game.ring import render
from game.states import TITLE, FIGHTING, ROUND_END, GAME_OVER, VICTORY, CALIBRATION
from cv.punch_detector import run_cv_thread

# Damage per punch when opponent is vulnerable
PUNCH_DAMAGE_BASE = 1
PUNCH_DAMAGE_STRENGTH_MULT = 0.0

# Webcam preview size (centered)
PREVIEW_WIDTH = 400
PREVIEW_HEIGHT = 300


def cv_frame_to_pygame(frame_bgr: np.ndarray, width: int, height: int) -> pygame.Surface:
    """Convert OpenCV BGR frame to pygame Surface, scaled to width x height."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    small = cv2.resize(rgb, (width, height))
    return pygame.image.frombuffer(small.tobytes(), (width, height), "RGB")


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption(TITLE)
    fullscreen = False

    # Shared state: CV thread -> game thread
    event_queue = queue.Queue()
    hand_state_ref = [{"blocking": False, "dodging": None}]  # mutable, updated by CV
    preview_ref = [None]  # latest webcam frame with hand landmarks
    stop_event = threading.Event()

    # Start CV thread
    cv_thread = threading.Thread(
        target=run_cv_thread,
        args=(event_queue, stop_event, hand_state_ref, preview_ref),
        daemon=True,
    )
    cv_thread.start()

    # Game state
    game_state = TITLE
    player = Player()
    opponent = Opponent()
    current_round = 1
    round_timer = 0.0
    round_end_player_won = None
    player_round_wins = 0
    countdown_timer = 3.0  # countdown before fight
    cv_error = None
    block_sustain_timer = 0.0  # hysteresis: keep block active briefly after CV drops

    clock = pygame.time.Clock()
    running = True

    while running:
        dt = clock.tick(60) / 1000.0

        # Process events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if fullscreen:
                        fullscreen = False
                        screen = pygame.display.set_mode(
                            (SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE
                        )
                    else:
                        running = False
                elif event.key == pygame.K_f:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode(
                            (0, 0), pygame.FULLSCREEN
                        )
                    else:
                        screen = pygame.display.set_mode(
                            (SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE
                        )
                elif event.key == pygame.K_SPACE:
                    if game_state == TITLE:
                        game_state = CALIBRATION
                        countdown_timer = 3.0
                    elif game_state == ROUND_END:
                        if round_end_player_won:
                            player_round_wins += 1
                        current_round += 1
                        if current_round > ROUNDS_TOTAL:
                            game_state = VICTORY if player_round_wins >= 2 else GAME_OVER
                        else:
                            player.reset()
                            opponent.reset(current_round)
                            round_timer = 0.0
                            game_state = FIGHTING
                elif event.key == pygame.K_r and game_state in (GAME_OVER, VICTORY):
                    game_state = TITLE
                    player = Player()
                    opponent = Opponent()
                    current_round = 1
                    round_timer = 0.0
                    player_round_wins = 0

        # Drain punch events from CV
        while True:
            try:
                ev = event_queue.get_nowait()
            except queue.Empty:
                break
            if ev.get("type") == "error":
                cv_error = ev.get("message", "CV error")
            elif ev.get("type") == "punch" and game_state == FIGHTING:
                hand = ev.get("hand", "left")
                strength = ev.get("strength", 0.5)
                if opponent.is_vulnerable:
                    damage = PUNCH_DAMAGE_BASE + strength * PUNCH_DAMAGE_STRENGTH_MULT * 10
                    opponent.take_damage(damage)

        # Update hand state for dodge/block (CV or keyboard B) during fight
        hs = hand_state_ref[0] if hand_state_ref else {}
        player.dodging = hs.get("dodging")
        if game_state == FIGHTING:
            cv_block = hs.get("blocking", False)
            block_key_held = pygame.key.get_pressed()[pygame.K_b]
            if cv_block or block_key_held:
                block_sustain_timer = BLOCK_SUSTAIN_SEC
            if block_sustain_timer > 0:
                block_sustain_timer -= dt
            # Effective block: (CV or key or sustained) and not in block cooldown
            player.blocking = (cv_block or block_key_held or block_sustain_timer > 0) and (
                player.block_cooldown_timer <= 0
            )
        else:
            player.blocking = False

        if game_state == CALIBRATION:
            countdown_timer -= dt
            if countdown_timer <= 0:
                game_state = FIGHTING
                player.reset()
                opponent.reset(1)
                round_timer = 0.0

        elif game_state == FIGHTING:
            player.update(dt)
            round_timer += dt
            attack = opponent.update(dt)
            if attack:
                # Player hit? Check dodge/block
                side = attack["side"]
                damage = attack["damage"]
                dodged = (
                    (side == PUNCH_LEFT and player.dodging == "right")
                    or (side == PUNCH_RIGHT and player.dodging == "left")
                )
                blocked = player.blocking
                if not dodged and not blocked:
                    player.take_damage(damage)
                elif blocked:
                    player.block_cooldown_timer = BLOCK_COOLDOWN_AFTER_HIT
            if not player.is_alive:
                game_state = GAME_OVER
            elif not opponent.is_alive:
                game_state = VICTORY
            elif round_timer >= ROUND_DURATION:
                game_state = ROUND_END
                round_end_player_won = player.hp > opponent.hp

        # Render
        if game_state == ROUND_END:
            render(
                screen, game_state, player, opponent,
                current_round, round_timer, round_end_player_won
            )
        elif game_state == CALIBRATION:
            render(
                screen, game_state, player, opponent,
                current_round, round_timer, None, countdown_timer
            )
        else:
            render(screen, game_state, player, opponent, current_round, round_timer)

        # Draw webcam preview with hand tracking (green dots), centered
        sw, sh = screen.get_width(), screen.get_height()
        if preview_ref[0] is not None and game_state in (TITLE, FIGHTING):
            try:
                preview_surf = cv_frame_to_pygame(
                    preview_ref[0], PREVIEW_WIDTH, PREVIEW_HEIGHT
                )
                px = (sw - PREVIEW_WIDTH) // 2
                py = sh - PREVIEW_HEIGHT - 30
                screen.blit(preview_surf, (px, py))
                pygame.draw.rect(screen, (128, 115, 153), (px, py, PREVIEW_WIDTH, PREVIEW_HEIGHT), 2)
            except Exception:
                pass

        if cv_error:
            font = pygame.font.Font(None, 24)
            err_surf = font.render(f"CV: {cv_error}", True, (255, 77, 77))
            screen.blit(err_surf, (10, sh - 25))
        pygame.display.flip()

    stop_event.set()
    cv_thread.join(timeout=2.0)
    pygame.quit()


if __name__ == "__main__":
    main()
