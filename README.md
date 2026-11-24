# Urban Rivals Agent v1

Local Chrome extension + Python 3.12 bridge for **Urban Rivals** WebGL matches (`Training vs Bots`, `EFC`, and `Tourney`). Plays once you are inside a match, with full per-star-level character & ability awareness across all 2,507+ official cards.

## Features

- **Per-Star-Level Card & Ability Resolution (`urban_rivals/star_catalog.py`)**: Uses all 2,507 official evolution pages (`1★` through `max★`), tracking exact stats, `ability_unlock_level`, and per-level ability text—with safe fallback for unmodeled bespoke abilities.
- **Three Match Formats (`urban_rivals/mode_policy.py`)**: Dedicated strategy tuning for **Training vs Bots**, **EFC**, and **Tourney**.
- **Advisor (Dry-Run HUD) & Auto-Play (`browser-extension/`)**:
  - **Advisor**: Displays a live floating HUD on the Urban Rivals tab with the recommended card, Pillz, Fury, and estimated win probability—no clicks.
  - **Auto-Play**: Dispatches calibrated clicks via `chrome.debugger` once inside a match. Press `Escape` or click `Stop` at any time.
- **Built-in Click-to-Calibrate Overlay**: Calibrate normalized `(0.0–1.0)` canvas click targets directly on the game tab in ~30 seconds.

## Quick Start (Windows + Python 3.12)

1. **Install Python dependencies** (use Python 3.12 in `.venv`, as `rapidocr-onnxruntime==1.4.4` requires `<3.13`):
   ```powershell
   .\Install-TrainingAgent.ps1
   ```
2. **Start the local bridge** (`127.0.0.1:8876`):
   ```powershell
   .\Start-TrainingAgent.ps1 -Execute -ReusePairingToken
   ```
   Copy the token from `local\pairing-token.txt`.
3. **Load the Chrome extension**:
   - Open `chrome://extensions`, enable **Developer mode**, and click **Load unpacked** → select `browser-extension/`.
   - Open `https://www.urban-rivals.com/game/play/webgl/`, enter a match, open the extension popup, paste your pairing token, run **Calibrate Canvas** once, and start **Advisor** or **Auto-Play**.

## Running Tests

```bash
python3 -m unittest discover -s tests
node --test browser-extension/*.test.js
```
