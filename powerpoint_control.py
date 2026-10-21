"""
powerpoint_control.py
─────────────────────
Presentation controller for Microsoft PowerPoint, Google Slides, and PDFs.

Gesture Mappings:
  • Point (Index Finger)        → Next Slide (Right / Space)
  • Peace (Two Fingers)         → Previous Slide (Left)
  • Pinch (Thumb + Index hold)  → Start Slideshow (F5)
  • Thumbs Up (👍 hold)         → End Slideshow (Escape)
  • OK Gesture (Hold 0.45s)     → Cycle Mode (Cursor -> Media -> Presentation)
"""

import time
import pyautogui

try:
    import win32com.client
    import win32gui
    import win32con
    _WIN32_AVAILABLE = True
except ImportError:
    _WIN32_AVAILABLE = False


class PowerPointController:
    """
    Robust presentation controller supporting:
    - Microsoft PowerPoint (COM Automation + Window Activation)
    - Browser / PDF presentations (Google Slides, Canva) via focused keys
    """

    COOLDOWN = 0.5   # Responsive navigation cooldown

    def __init__(self):
        self._ppt      = None
        self._last_cmd = 0
        self._try_connect()

    # ─── public ───────────────────────────────────────────────────────

    def next_slide(self):
        if not self._cooldown_ok():
            return
        self._touch()
        
        # 1. Try COM first
        if self._ppt_active():
            try:
                if self._ppt.SlideShowWindows.Count > 0:
                    self._ppt.SlideShowWindows(1).View.Next()
                    return
                elif self._ppt.ActiveWindow:
                    self._ppt.ActiveWindow.View.Next()
                    return
            except Exception:
                pass

        # 2. Focus window & press Right arrow
        self._focus_presentation_window()
        pyautogui.press('right')

    def previous_slide(self):
        if not self._cooldown_ok():
            return
        self._touch()

        # 1. Try COM first
        if self._ppt_active():
            try:
                if self._ppt.SlideShowWindows.Count > 0:
                    self._ppt.SlideShowWindows(1).View.Previous()
                    return
                elif self._ppt.ActiveWindow:
                    self._ppt.ActiveWindow.View.Previous()
                    return
            except Exception:
                pass

        # 2. Focus window & press Left arrow
        self._focus_presentation_window()
        pyautogui.press('left')

    def start_slideshow(self):
        """Start the slideshow (F5)."""
        if not self._cooldown_ok():
            return
        self._touch()
        if self._ppt_active():
            try:
                self._ppt.ActivePresentation.SlideShowSettings.Run()
                return
            except Exception:
                pass
        self._focus_presentation_window()
        pyautogui.press('f5')

    def end_slideshow(self):
        """End the slideshow (Escape)."""
        if not self._cooldown_ok():
            return
        self._touch()
        if self._ppt_active():
            try:
                if self._ppt.SlideShowWindows.Count > 0:
                    self._ppt.SlideShowWindows(1).View.Exit()
                    return
            except Exception:
                pass
        self._focus_presentation_window()
        pyautogui.press('escape')

    def current_slide_info(self) -> str:
        """Return 'Slide X / Y' or empty string."""
        if self._ppt_active():
            try:
                if self._ppt.SlideShowWindows.Count > 0:
                    sw  = self._ppt.SlideShowWindows(1)
                    cur = sw.View.CurrentShowPosition
                    tot = self._ppt.ActivePresentation.Slides.Count
                    return f"Slide {cur} / {tot}"
                elif self._ppt.ActiveWindow:
                    cur = self._ppt.ActiveWindow.View.Slide.SlideIndex
                    tot = self._ppt.ActivePresentation.Slides.Count
                    return f"Slide {cur} / {tot}"
            except Exception:
                pass
        return ""

    def _focus_presentation_window(self):
        """Finds and foregrounds PowerPoint or fullscreen slideshow window."""
        if not _WIN32_AVAILABLE:
            return
        def enum_cb(hwnd, matches):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                # Match PowerPoint slideshow or presentation
                if "powerpoint slide show" in title or "diaporama powerpoint" in title:
                    matches.insert(0, hwnd)  # High priority: running slideshow
                elif "powerpoint" in title or ".pptx" in title:
                    matches.append(hwnd)
        matches = []
        try:
            win32gui.EnumWindows(enum_cb, matches)
            if matches:
                target_hwnd = matches[0]
                win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(target_hwnd)
                time.sleep(0.04)
        except Exception:
            pass

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
