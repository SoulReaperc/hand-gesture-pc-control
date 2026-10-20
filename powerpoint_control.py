"""
powerpoint_control.py
─────────────────────
Microsoft PowerPoint slide navigation via:
  • win32com automation (if PowerPoint is running), OR
  • keyboard shortcuts (Right/Left arrow keys) as fallback.

Gesture triggers are decided in main.py.
"""

import time
import pyautogui

# Try win32com for direct PPT control
try:
    import win32com.client
    _WIN32_AVAILABLE = True
except ImportError:
    _WIN32_AVAILABLE = False


class PowerPointController:
    """
    Navigate PowerPoint slides: next, previous.
    Tries COM automation first, falls back to keyboard arrows.
    """

    COOLDOWN = 0.8   # seconds between slide changes

    def __init__(self):
        self._ppt      = None
        self._last_cmd = 0
        self._try_connect()

    # ─── public ───────────────────────────────────────────────────────

    def next_slide(self):
        if not self._cooldown_ok():
            return
        self._touch()
        if self._ppt_active():
            try:
                sw = self._ppt.ActivePresentation.SlideShowWindow
                sw.View.Next()
                return
            except Exception:
                pass
        # Fallback
        pyautogui.press('right')

    def previous_slide(self):
        if not self._cooldown_ok():
            return
        self._touch()
        if self._ppt_active():
            try:
                sw = self._ppt.ActivePresentation.SlideShowWindow
                sw.View.Previous()
                return
            except Exception:
                pass
        pyautogui.press('left')

    def start_slideshow(self):
        """Start the slideshow from beginning (F5)."""
        if not self._cooldown_ok():
            return
        self._touch()
        if self._ppt_active():
            try:
                self._ppt.ActivePresentation.SlideShowSettings.Run()
                return
            except Exception:
                pass
        pyautogui.press('f5')

    def end_slideshow(self):
        """End the slideshow (Escape)."""
        if not self._cooldown_ok():
            return
        self._touch()
        pyautogui.press('escape')

    def current_slide_info(self) -> str:
        """Return 'Slide X / Y' or empty string."""
        if self._ppt_active():
            try:
                sw  = self._ppt.ActivePresentation.SlideShowWindow
                cur = sw.View.CurrentShowPosition
                tot = self._ppt.ActivePresentation.Slides.Count
                return f"Slide {cur} / {tot}"
            except Exception:
                pass
        return ""

    def reconnect(self):
        """Re-try COM connection (call if PPT was opened after app start)."""
        self._try_connect()

    # ─── private ──────────────────────────────────────────────────────

    def _try_connect(self):
        if not _WIN32_AVAILABLE:
            return
        try:
            self._ppt = win32com.client.GetActiveObject("PowerPoint.Application")
        except Exception:
            self._ppt = None

    def _ppt_active(self) -> bool:
        if not _WIN32_AVAILABLE or self._ppt is None:
            return False
        try:
            _ = self._ppt.Version   # simple property access to test liveness
            return True
        except Exception:
            self._ppt = None
            return False

    def _cooldown_ok(self) -> bool:
        return time.time() - self._last_cmd >= self.COOLDOWN

    def _touch(self):
        self._last_cmd = time.time()
