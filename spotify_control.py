"""
spotify_control.py
──────────────────
Spotify playback control using keyboard media keys.
Works whenever the Spotify desktop app (or any media player) is open.
No API credentials needed.

Gesture triggers are decided in main.py; this module just acts.
"""

import time
import pyautogui


class SpotifyController:
    """
    Controls Spotify via Windows media keyboard shortcuts.
    Works with the Spotify desktop app open — no API needed.
    """

    COOLDOWN = 1.5   # seconds between commands

    def __init__(self):
        self._last_cmd = 0
        print("[Spotify] Using keyboard media keys (no API required).")

    # ─── public ───────────────────────────────────────────────────────

    def next_track(self):
        if not self._cooldown_ok():
            return
        self._touch()
        pyautogui.press('nexttrack')

    def previous_track(self):
        if not self._cooldown_ok():
            return
        self._touch()
        pyautogui.press('prevtrack')

    def play_pause(self):
        if not self._cooldown_ok():
            return
        self._touch()
        pyautogui.press('playpause')

    def current_track_info(self) -> str:
        """Returns empty string — keyboard-only mode has no track metadata."""
        return ""

    # ─── private ──────────────────────────────────────────────────────

    def _cooldown_ok(self) -> bool:
        return time.time() - self._last_cmd >= self.COOLDOWN

    def _touch(self):
        self._last_cmd = time.time()
