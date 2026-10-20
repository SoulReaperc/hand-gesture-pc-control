"""
mouse_control.py
────────────────
Mouse movement, click, double-click, right-click and scroll
via hand landmarks, using pyautogui.

Gesture mapping (default):
  Index up only              →  move mouse (index tip → screen coords)
  Index + Middle up, close   →  left click  (tips close together)
  Fist, move up/down         →  scroll
  Pinky up only              →  right click
  Three fingers up           →  double click
"""

import pyautogui
import numpy as np
import time

pyautogui.FAILSAFE = False   # prevent corner crash
pyautogui.PAUSE    = 0       # no auto-delay


class MouseController:
    """
    Converts hand-landmark coordinates to mouse actions.

    *cam_w*, *cam_h*: camera frame dimensions.
    *screen_w*, *screen_h*: target screen dimensions.
    The active control region is defined by MARGIN (fraction of frame
    edges excluded to avoid jitter near borders).
    """

    MARGIN          = 0.33    # 33 % border exclusion (high sensitivity)
    SMOOTHING       = 3       # low-lag moving average
    CLICK_DIST      = 35      # pixel distance → trigger click
    CLICK_COOLDOWN  = 0.4     # seconds between clicks
    SCROLL_SPEED    = 3       # scroll notches per gesture cycle
    SCROLL_COOLDOWN = 0.15

    def __init__(self, cam_w=640, cam_h=480):
        import pyautogui
        self.cam_w  = cam_w
        self.cam_h  = cam_h
        self.screen_w, self.screen_h = pyautogui.size()

        self._prev_x = self.screen_w  // 2
        self._prev_y = self.screen_h  // 2
        self._last_click_time  = 0
        self._last_scroll_time = 0
        self._prev_index_y     = None   # for scroll direction

    # ─── public ───────────────────────────────────────────────────────

    def move(self, index_x: int, index_y: int):
        """Map camera index-tip coords to screen coords and move mouse."""
        # Exclude margin region
        m = self.MARGIN
        xi = np.interp(index_x,
                       [int(self.cam_w * m), int(self.cam_w * (1-m))],
                       [0, self.screen_w])
        yi = np.interp(index_y,
                       [int(self.cam_h * m), int(self.cam_h * (1-m))],
                       [0, self.screen_h])
        xi, yi = int(np.clip(xi, 0, self.screen_w-1)), \
                 int(np.clip(yi, 0, self.screen_h-1))

        # Smooth movement
        sx = self._prev_x + (xi - self._prev_x) / self.SMOOTHING
        sy = self._prev_y + (yi - self._prev_y) / self.SMOOTHING
        self._prev_x, self._prev_y = sx, sy

        import pyautogui
        pyautogui.moveTo(int(sx), int(sy))

    def left_click(self):
        if time.time() - self._last_click_time > self.CLICK_COOLDOWN:
            import pyautogui
            pyautogui.click()
            self._last_click_time = time.time()

    def right_click(self):
        if time.time() - self._last_click_time > self.CLICK_COOLDOWN:
            import pyautogui
            pyautogui.rightClick()
            self._last_click_time = time.time()

    def double_click(self):
        if time.time() - self._last_click_time > self.CLICK_COOLDOWN:
            import pyautogui
            pyautogui.doubleClick()
            self._last_click_time = time.time()

    def scroll(self, index_y: int):
        """
        Detect scroll direction from vertical movement of index tip.
        *index_y* is the current pixel y-coordinate of the index tip.
        """
        if time.time() - self._last_scroll_time < self.SCROLL_COOLDOWN:
            return

        import pyautogui
        if self._prev_index_y is not None:
            dy = index_y - self._prev_index_y
            if dy < -15:       # hand moving UP → scroll UP
                pyautogui.scroll(self.SCROLL_SPEED)
                self._last_scroll_time = time.time()
            elif dy > 15:      # hand moving DOWN → scroll DOWN
                pyautogui.scroll(-self.SCROLL_SPEED)
                self._last_scroll_time = time.time()
        self._prev_index_y = index_y

    def is_click_distance(self, dist: float) -> bool:
        return dist < self.CLICK_DIST
