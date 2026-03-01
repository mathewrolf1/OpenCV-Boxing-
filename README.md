# Fight Brandon - CV Boxing

Punch Out-style boxing game that uses your webcam to detect punches, blocks, and dodges. You fight an AI opponent with telegraphs, vulnerability windows, and animated GIF sprites.

## Features

- **Computer vision controls**: Punch toward the camera, dodge left/right, block with a guard pose.
- **Opponent AI**: Telegraphs, attacks, vulnerability windows, and hit-stun.
- **Animated enemy**: GIF-based animations for idle, wind-up, punch, vulnerable, and hit.
- **Full-screen toggle**: Press `F` during play.
- **HUD feedback**: HP bars with segment lines, block indicator, HIT text, and QR code on win/lose.

## Requirements

- Python 3.11+
- Webcam
- Good lighting (improves hand detection)

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Controls

- **SPACE** - Start fight (title) / Continue (round end)
- **B** - Block (keyboard fallback)
- **F** - Toggle fullscreen
- **R** - Restart (game over / victory)
- **ESC** - Quit (or exit fullscreen)

## How to Play

1. **Punch** - Make a fist and punch toward the camera to attack when the opponent is hittable (green box).
2. **Dodge** - Move your hands to the left or right side of the frame to dodge incoming punches.
3. **Block** - Raise both hands high and close together to block. Dots turn blue when blocking.
4. Watch for **telegraphs** - The opponent turns reddish before attacking. Dodge or block.
5. Win 2 of 3 rounds to claim victory.

## Assets

Put assets in `assets/`:

- **Background**: `assets/background.png`
- **QR code**: `assets/qrcode.png`
- **Enemy GIFs**: `assets/brandon_enemy/`
  - `brandonidle.gif`
  - `brandonwind.gif`
  - `brandonpunch.gif`
  - `brandonvunerable.gif`
  - `brandonhit.gif`

## Troubleshooting

- **Webcam permission**: On macOS, allow Camera access for Terminal/Cursor in **System Settings → Privacy & Security → Camera**.
- **MediaPipe install issues**: Use Python 3.11 (MediaPipe does not support 3.13).
- **Frozen webcam during countdown**: The preview is hidden during the countdown by design.

## Project Layout

```
brandongame/
├── main.py
├── requirements.txt
├── cv/               # webcam + hand tracking + punch detection
├── game/             # AI, rendering, states
└── assets/           # background, QR, enemy GIFs
```
