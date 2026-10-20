"""
main.py  ─  Gesture Control System
════════════════════════════════════════════════════════════════════════
Python 3.12 | MediaPipe Tasks 1.0 | OpenCV | pycaw | pyautogui | win32com

Run:  python main.py
Keys: Q/Esc=quit  M=next mode  H=help  S=screenshot  R=PPT reconnect

════════════════════════════════════════════════════════════════════════
GESTURE REFERENCE
─────────────────────────────────────────────────────────────────────
▶ AUTO MODE  (default — mouse + volume work together, no switching)

  VOLUME:
    All 5 fingers SPREAD WIDE apart (fan shape) to activate.
    Rotate hand  CLOCKWISE          →  Volume UP
    Rotate hand  ANTI-CLOCKWISE     →  Volume DOWN
    Spread-open → close to FIST → hold 1 s  →  Mute toggle

  MOUSE:
    Index finger up (ring + pinky down)  →  Move cursor
    Index + Middle tips PINCH close      →  Left click
    Thumb + Index  tips PINCH close      →  Right click
    3 fingers up + move hand up / down  →  Scroll

▶ SPOTIFY MODE  (press M)
    Index swipe RIGHT   →  Next track
    Index swipe LEFT    →  Previous track
    Index + Pinky UP (ONLY) →  Play / Pause

▶ POWERPOINT MODE  (press M again)
    Index+Middle swipe RIGHT  →  Next slide
    Index+Middle swipe LEFT   →  Previous slide
    Open hand hold 0.5 s      →  Start slideshow
    Fist hold 1 s             →  End slideshow
════════════════════════════════════════════════════════════════════════
"""

import cv2
import time
import sys
import math
import numpy as np
import pyautogui

from gesture_detector   import GestureDetector
from volume_control     import VolumeController
from mouse_control      import MouseController
from spotify_control    import SpotifyController
from powerpoint_control import PowerPointController

pyautogui.FAILSAFE = False
pyautogui.PAUSE    = 0

# ── Config ─────────────────────────────────────────────────────────────
CAM_INDEX = 0
CAM_W     = 1280
CAM_H     = 720
WIN_NAME  = "Gesture Control System"

MODES = ["AUTO", "SPOTIFY", "POWERPOINT"]
MODE_COLORS = {
    "AUTO":       (255, 200,  50),
    "SPOTIFY":    ( 80, 255,  80),
    "POWERPOINT": (255, 120,  50),
}

# Volume
SPREAD_MIN_PX  = 160   # min thumb-tip to pinky-tip distance to count as "spread"
ROT_STEP_DEG   = 18    # degrees per volume step
VOL_STEP_PCT   = 2     # % per step
ROT_DEAD_DEG   = 5     # ignore jitter below this

# Mouse Sensitivity Configuration (Higher margin = less physical hand movement needed)
MOUSE_MARGIN_X = 0.33    # 33% margin left/right (active region is central 34%)
MOUSE_MARGIN_Y = 0.32    # 32% margin top/bottom (active region is central 36%)
MOUSE_SMOOTH   = 2.5     # Low lag, highly responsive cursor tracking
CLICK_DIST     = 38
CLICK_COOL     = 0.45
SCROLL_COOL    = 0.12

# Swipe
SWIPE_WIN      = 15
SWIPE_PX       = 85

# Holds
FIST_HOLD      = 1.0
OPEN_HOLD      = 0.5


# ══════════════════════════════════════════════════════════════════════
class GestureApp:

    def __init__(self):
        self.cap = self._open_cam()
        self.detector = GestureDetector(max_hands=1,
                                        detection_con=0.75,
                                        tracking_con=0.75)
        self.volume   = VolumeController()
        self.spotify  = SpotifyController()
        self.ppt      = PowerPointController()

        # Mode
        self.mode_idx  = 0
        self.mode      = MODES[self.mode_idx]
        self.show_help = True

        # Flash
        self.flash_msg  = ""
        self.flash_time = 0.0

        # ── Volume state ──────────────────────────────────────────
        self._vol_pct        = self.volume.get_volume_pct()
        self._angle_buf      : list[float] = []
        self._rot_accum      = 0.0
        self._last_spread_t  = 0.0        # timestamp when hand was last spread open
        self._vol_fist_t     = None
        self._fist_loss_t    = None       # timer for grace period during mute hold
        self._mute_holding   = False
        self._mute_cooldown  = 0.0        # timestamp until which scrolling is blocked after mute

        # ── Mouse state ───────────────────────────────────────────
        sw, sh = pyautogui.size()
        self._mx = float(sw // 2)
        self._my = float(sh // 2)
        self._last_lclick   = 0.0
        self._last_rclick   = 0.0
        self._last_scroll   = 0.0
        self._scroll_ref_y  = None
        self._scroll_prev_y = None

        # ── Swipe / Spotify / PPT state ───────────────────────────
        self._swipe_x          : list[int] = []
        self._last_spotify_pp  = 0.0
        self._open_t           = None
        self._ppt_fist_t       = None

    # ──────────────────────────────────────────────────────────────────
    def _open_cam(self):
        cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)
        cap.set(cv2.CAP_PROP_FPS, 30)
        if not cap.isOpened():
            sys.exit("[ERROR] Cannot open webcam.")
        return cap

    # ──────────────────────────────────────────────────────────────────
    def run(self):
        print("[INFO] Gesture Control | Q=quit  M=mode  H=help")
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)

            frame = self.detector.process(frame, draw=True)
            lm    = self.detector.lm_list

            if lm:
                palm_facing = self.detector.is_palm_facing()
                if palm_facing:
                    fingers = self.detector.fingers_up()
                    gesture = self.detector.get_gesture_name(fingers)
                    if   self.mode == "AUTO":       self._auto_mode(frame, fingers, lm)
                    elif self.mode == "SPOTIFY":    self._spotify_mode(frame, fingers, lm)
                    elif self.mode == "POWERPOINT": self._ppt_mode(frame, fingers, lm)
                else:
                    fingers = [False] * 5
                    gesture = "Back of Hand (Show Palm)"
                    self._reset_vol()
                    self._scroll_ref_y  = None
                    self._scroll_prev_y = None
            else:
                fingers = [False] * 5
                gesture = "No Hand"
                self._reset_vol()
                self._scroll_ref_y  = None
                self._scroll_prev_y = None

            frame = self._draw_hud(frame, fingers, gesture)
            cv2.imshow(WIN_NAME, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):
                break
            elif key == ord('m'):
                self.mode_idx = (self.mode_idx + 1) % len(MODES)
                self.mode = MODES[self.mode_idx]
                self._reset_vol()
                self._swipe_x.clear()
                self._flash(f"MODE → {self.mode}")
            elif key == ord('h'):
                self.show_help = not self.show_help
            elif key == ord('s'):
                fn = f"shot_{int(time.time())}.png"
                cv2.imwrite(fn, frame)
                self._flash(f"Saved {fn}")
            elif key == ord('r'):
                self.ppt.reconnect()
                self._flash("PPT reconnected")

        self.cap.release()
        cv2.destroyAllWindows()

    # ══════════════════════════════════════════════════════════════════
    # AUTO MODE  — volume + mouse simultaneously
    # ══════════════════════════════════════════════════════════════════
    def _auto_mode(self, frame, fingers, lm):
        T, I, M, R, P = fingers
        fist      = not any(fingers)
        three_up  = (not T) and I and M and R and (not P)   # [0,1,1,1,0]
        is_spread = self._is_spread_open(fingers, lm)
        now       = time.time()

        # Dynamic hand-scale distance threshold for clicks (35% of palm size)
        palm_size       = self.detector.get_palm_size()
        click_threshold = max(18.0, palm_size * 0.35)

        # ─── VOLUME & MUTE: volume dial or spread->fist mute sequence ──────────
        self._do_volume(frame, fingers, lm, fist, is_spread)

        # Skip mouse/scroll while hand is spread, holding mute, in mute cooldown, or recently spread
        if is_spread or self._mute_holding or (now < self._mute_cooldown) or (now - self._last_spread_t < 1.0):
            return

        # ─── MOUSE: index up + ring&pinky down ───────────────────
        if I and not R and not P and not three_up:
            self._do_mouse_move(frame, lm)

        # Left click: index + middle tips pinch (dynamic hand scale)
        if I and M and not R and not P:
            d, frame, info = self.detector.distance(8, 12, frame, draw=True)
            self._draw_pinch_dot(frame, info, d, click_threshold, green=True)
            if d < click_threshold and time.time() - self._last_lclick > CLICK_COOL:
                pyautogui.click()
                self._last_lclick = time.time()
                self._flash("Left Click ✓")

        # Right click: thumb + index tips pinch (dynamic hand scale)
        if T and I and not M and not R and not P:
            d, frame, info = self.detector.distance(4, 8, frame, draw=True)
            self._draw_pinch_dot(frame, info, d, click_threshold, green=False)
            if d < click_threshold and time.time() - self._last_rclick > CLICK_COOL:
                pyautogui.rightClick()
                self._last_rclick = time.time()
                self._flash("Right Click ✓")

        # ─── SCROLL (3 fingers up + move hand up/down) ───────────
        if three_up:
            self._do_scroll(frame, lm, three_up=three_up)
        else:
            self._scroll_prev_y = None

        # Guide
        h, w = frame.shape[:2]
        cv2.putText(frame,
                    "Index=Move | I+M=LClick | T+I=RClick | 3-Fingers UP=Scroll",
                    (10, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 200, 50), 1)
        cv2.putText(frame,
                    "Spread 5 fingers wide=Volume | Spread→Fist 1s=Mute",
                    (10, h - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 200, 255), 1)

    # ──────────────────────────────────────────────────────────────────
    def _is_spread_open(self, fingers, lm) -> bool:
        """
        True only when ALL 5 fingers are UP *and* fingers are SPREAD WIDE.
        Span threshold scales dynamically with palm_size (1.30x palm size).
        """
        if not all(fingers):
            return False
        if len(lm) < 21:
            return False
        tx, ty = lm[4][1],  lm[4][2]
        px, py = lm[20][1], lm[20][2]
        span = math.hypot(px - tx, py - ty)
        palm_size = self.detector.get_palm_size()
        return span >= (palm_size * 1.30)

    # ──────────────────────────────────────────────────────────────────
    def _do_volume(self, frame, fingers, lm, fist, is_spread):
        """
        Called in AUTO mode.
        Spread open → Rotate CW = UP, CCW = DOWN.
        Spread → Fist → hold 1 s → Mute toggle.
        """
        now = time.time()
        if is_spread:
            self._last_spread_t = now
            self._mute_holding  = False
            self._vol_fist_t    = None
            self._fist_loss_t   = None

        recently_spread = (now - self._last_spread_t) < 1.5
        # Accept tight fist, fist with thumb resting, or claw gesture for mute
        fist_like = fist or (sum(fingers) <= 1) or self.detector.is_claw()

        # Mute sequence: was spread open recently, now closed into fist
        if recently_spread and (fist_like or self._mute_holding):
            # User intentionally opened hand completely -> cancel mute hold
            if sum(fingers) >= 3 or is_spread:
                self._mute_holding = False
                self._vol_fist_t   = None
                self._fist_loss_t  = None
            else:
                if fist_like:
                    self._fist_loss_t = None
                else:  # momentary flicker (e.g. 2 fingers detected briefly)
                    if self._fist_loss_t is None:
                        self._fist_loss_t = now
                    elif now - self._fist_loss_t > 0.35:  # lost fist for > 350ms -> cancel
                        self._mute_holding = False
                        self._vol_fist_t   = None

                if self._mute_holding or fist_like:
                    self._mute_holding = True
                    if self._vol_fist_t is None:
                        self._vol_fist_t = now

                    elapsed = now - self._vol_fist_t
                    self._draw_hold_bar(frame, elapsed, FIST_HOLD, "Hold for MUTE")
                    if elapsed >= FIST_HOLD:
                        self.volume.toggle_mute()
                        self._flash("Mute Toggled ✓")
                        self._reset_vol()
                        self._mute_cooldown = now + 1.5   # block scroll for 1.5s after mute
                        return
        elif not is_spread:
            self._mute_holding = False
            self._vol_fist_t   = None
            self._fist_loss_t  = None
            self._angle_buf.clear()
            self._rot_accum = 0.0

        # Rotation
        if not is_spread:
            self._draw_vol_dial(frame, None)
            return

        angle = self._hand_angle(lm)
        self._angle_buf.append(angle)
        if len(self._angle_buf) > 6:
            self._angle_buf.pop(0)

        if len(self._angle_buf) >= 3:
            delta = self._angle_delta(self._angle_buf[-3], self._angle_buf[-1])
            if abs(delta) > ROT_DEAD_DEG / 3:
                self._rot_accum += delta
            steps = int(self._rot_accum / ROT_STEP_DEG)
            if steps != 0:
                self._rot_accum -= steps * ROT_STEP_DEG
                change  = steps * VOL_STEP_PCT
                new_pct = int(np.clip(self._vol_pct + change, 0, 100))
                self.volume._set_volume_pct(new_pct)
                self._vol_pct = new_pct
                arrow = "▲" if change > 0 else "▼"
                self._flash(f"{arrow} Volume {new_pct}%")

        self._draw_vol_dial(frame, angle)

        # Label
        h, w = frame.shape[:2]
        cv2.putText(frame, "VOLUME: Rotate CW=UP  CCW=DOWN",
                    (10, h - 50), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (0, 200, 255), 2)

    def _reset_vol(self):
        self._angle_buf.clear()
        self._rot_accum   = 0.0
        self._mute_holding = False
        self._vol_fist_t  = None
        self._fist_loss_t = None

    def _hand_angle(self, lm) -> float:
        wx, wy = lm[0][1], lm[0][2]
        mx, my = lm[9][1], lm[9][2]
        return math.degrees(math.atan2(my - wy, mx - wx))

    def _angle_delta(self, a1: float, a2: float) -> float:
        d = a2 - a1
        if d >  180: d -= 360
        if d < -180: d += 360
        return d       # positive = CW = volume UP

    # ──────────────────────────────────────────────────────────────────
    def _do_mouse_move(self, frame, lm):
        sw, sh = pyautogui.size()
        ix, iy = lm[8][1], lm[8][2]
        mx = MOUSE_MARGIN_X
        my = MOUSE_MARGIN_Y
        tx = np.interp(ix, [int(CAM_W * mx), int(CAM_W * (1 - mx))], [0, sw - 1])
        ty = np.interp(iy, [int(CAM_H * my), int(CAM_H * (1 - my))], [0, sh - 1])
        tx = float(np.clip(tx, 0, sw - 1))
        ty = float(np.clip(ty, 0, sh - 1))
        self._mx += (tx - self._mx) / MOUSE_SMOOTH
        self._my += (ty - self._my) / MOUSE_SMOOTH
        pyautogui.moveTo(int(round(self._mx)), int(round(self._my)))
        cv2.circle(frame, (ix, iy), 14, (50, 255, 130), cv2.FILLED)
        cv2.circle(frame, (ix, iy), 14, (0, 0, 0), 1)

    def _do_scroll(self, frame, lm, three_up: bool):
        """
        Smooth, natural directional scrolling based on physical hand movement (dy) when holding 3 fingers up:
        Normalized relative to palm_size for distance-invariant scrolling.
        """
        hand_y = lm[9][2]   # Middle MCP landmark y coordinate
        if self._scroll_prev_y is None:
            self._scroll_prev_y = hand_y
            return

        dy = hand_y - self._scroll_prev_y
        self._scroll_prev_y = hand_y

        now = time.time()
        cool = 0.09        # Controlled scroll interval (~11 scroll actions/sec max)

        if now - self._last_scroll < cool:
            return

        palm_size = self.detector.get_palm_size()
        norm_dy = (dy / max(1.0, palm_size)) * 100.0

        # Direction and speed based on normalized physical hand movement
        if norm_dy < -2.5:        # Hand moving UP
            scroll_dir = 1  # Scroll UP
            speed = abs(norm_dy)
            scroll_amount = int(np.clip(1 + speed * 0.20, 1, 5))
            msg = f"Scroll UP (⚡{scroll_amount})" if scroll_amount > 2 else "Scroll UP"
        elif norm_dy > 2.5:       # Hand moving DOWN
            scroll_dir = -1 # Scroll DOWN
            speed = abs(norm_dy)
            scroll_amount = int(np.clip(1 + speed * 0.20, 1, 5))
            msg = f"Scroll DOWN (⚡{scroll_amount})" if scroll_amount > 2 else "Scroll DOWN"
        else:              # Stationary hand with 3 fingers up held
            scroll_dir = 1
            scroll_amount = 1
            msg = "Scroll UP (Slow)"

        pyautogui.scroll(scroll_dir * scroll_amount)
        self._last_scroll = now
        self._flash(msg)

    def _draw_pinch_dot(self, frame, info, dist, threshold, green: bool):
        if not info:
            return
        ratio = max(0.0, 1.0 - dist / max(1.0, threshold))
        c = int(255 * ratio)
        col = (0, c, 255 - c) if green else (c, 0, 255 - c)
        cv2.circle(frame, (info[4], info[5]), 10, col, cv2.FILLED)

    # ══════════════════════════════════════════════════════════════════
    # SPOTIFY MODE
    # ══════════════════════════════════════════════════════════════════
    def _spotify_mode(self, frame, fingers, lm):
        T, I, M, R, P = fingers
        ix = lm[8][1]
        palm_size = self.detector.get_palm_size()
        swipe_threshold = max(40.0, palm_size * 0.60)

        # Play / Pause: ONLY Index + Pinky UP ([0, 1, 0, 0, 1])
        index_pinky_only = I and P and (not T) and (not M) and (not R)
        if index_pinky_only:
            now = time.time()
            if now - self._last_spotify_pp > 0.8:
                self.spotify.play_pause()
                self._flash("⏯  Play / Pause")
                self._last_spotify_pp = now
            self._swipe_x.clear()
            return

        # Swipe NEXT / PREV track (Index UP without Pinky)
        if I and not P:
            self._swipe_x.append(ix)
            if len(self._swipe_x) > SWIPE_WIN:
                self._swipe_x.pop(0)
            if len(self._swipe_x) == SWIPE_WIN:
                dx = self._swipe_x[-1] - self._swipe_x[0]
                if dx > swipe_threshold:
                    self.spotify.next_track()
                    self._flash("⏭  Next Track")
                    self._swipe_x.clear()
                elif dx < -swipe_threshold:
                    self.spotify.previous_track()
                    self._flash("⏮  Previous Track")
                    self._swipe_x.clear()
        else:
            self._swipe_x.clear()

        h, w = frame.shape[:2]
        cv2.putText(frame,
                    "Swipe RIGHT=Next | Swipe LEFT=Prev | Index+Pinky UP=Play/Pause",
                    (10, h - 50), cv2.FONT_HERSHEY_SIMPLEX,
                    0.48, (80, 255, 80), 1)

    # ══════════════════════════════════════════════════════════════════
    # POWERPOINT MODE
    # ══════════════════════════════════════════════════════════════════
    def _ppt_mode(self, frame, fingers, lm):
        T, I, M, R, P = fingers
        ix   = lm[8][1]
        all5 = all(fingers)
        fist = not any(fingers)
        palm_size = self.detector.get_palm_size()
        swipe_threshold = max(40.0, palm_size * 0.60)

        if I and M:
            self._swipe_x.append(ix)
            if len(self._swipe_x) > SWIPE_WIN:
                self._swipe_x.pop(0)
            if len(self._swipe_x) == SWIPE_WIN:
                dx = self._swipe_x[-1] - self._swipe_x[0]
                if dx > swipe_threshold:
                    self.ppt.next_slide()
                    self._flash("▶ Next Slide")
                    self._swipe_x.clear()
                elif dx < -swipe_threshold:
                    self.ppt.previous_slide()
                    self._flash("◀ Previous Slide")
                    self._swipe_x.clear()
        else:
            self._swipe_x.clear()

        if all5:
            if self._open_t is None:
                self._open_t = time.time()
            else:
                e = time.time() - self._open_t
                self._draw_hold_bar(frame, e, OPEN_HOLD, "Hold → Start Slideshow")
                if e >= OPEN_HOLD:
                    self.ppt.start_slideshow()
                    self._flash("PPT: Started ▶")
                    self._open_t = None
        else:
            self._open_t = None

        if fist:
            if self._ppt_fist_t is None:
                self._ppt_fist_t = time.time()
            else:
                e = time.time() - self._ppt_fist_t
                self._draw_hold_bar(frame, e, FIST_HOLD, "Hold → End Slideshow")
                if e >= FIST_HOLD:
                    self.ppt.end_slideshow()
                    self._flash("PPT: Ended ■")
                    self._ppt_fist_t = None
        else:
            self._ppt_fist_t = None

        info = self.ppt.current_slide_info()
        h, w = frame.shape[:2]
        if info:
            cv2.putText(frame, info, (10, h - 75),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 120, 50), 2)
        cv2.putText(frame,
                    "2-Finger Swipe=Slide | OpenHand=Start | Fist=End",
                    (10, h - 50), cv2.FONT_HERSHEY_SIMPLEX,
                    0.48, (255, 120, 50), 1)

    # ══════════════════════════════════════════════════════════════════
    # HUD
    # ══════════════════════════════════════════════════════════════════
    def _draw_hud(self, frame, fingers, gesture):
        h, w = frame.shape[:2]
        color = MODE_COLORS.get(self.mode, (200, 200, 200))

        # Top bar
        ovl = frame.copy()
        cv2.rectangle(ovl, (0, 0), (w, 62), (10, 10, 15), -1)
        cv2.addWeighted(ovl, 0.70, frame, 0.30, 0, frame)

        # Mode badge
        badge = f"  {self.mode}  "
        (bw, _), _ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_DUPLEX, 0.9, 2)
        bx = (w - bw) // 2
        cv2.rectangle(frame, (bx-10, 4), (bx+bw+10, 58),
                      tuple(int(c*0.35) for c in color), -1)
        cv2.rectangle(frame, (bx-10, 4), (bx+bw+10, 58), color, 2)
        cv2.putText(frame, badge, (bx, 46),
                    cv2.FONT_HERSHEY_DUPLEX, 0.9, color, 2)

        # FPS
        cv2.putText(frame, f"FPS:{int(self.detector.fps)}", (8, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 100), 2)

        # Gesture name / Out of frame warning
        if self.detector.lm_list and not self.detector.is_fully_visible(margin=0.04):
            cv2.putText(frame, "⚠ Hand Out of Frame (Actions Paused)", (8, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
        else:
            cv2.putText(frame, gesture, (8, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 2)

        # Finger dots
        labels = ["T", "I", "M", "R", "P"]
        for i, (up, lab) in enumerate(zip(fingers, labels)):
            cx = 20 + i * 40
            cy = h - 30
            col = (0, 255, 100) if up else (60, 60, 60)
            cv2.circle(frame, (cx, cy), 14, col, -1)
            cv2.circle(frame, (cx, cy), 14, (0, 0, 0), 1)
            cv2.putText(frame, lab, (cx-6, cy+5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)

        # Flash message
        if self.flash_msg:
            age = time.time() - self.flash_time
            if age < 2.0:
                a = max(0.0, 1.0 - age / 2.0)
                col = tuple(int(c*a) for c in (0, 255, 200))
                cv2.putText(frame, self.flash_msg,
                            (w//2 - 220, h//2 - 20),
                            cv2.FONT_HERSHEY_DUPLEX, 1.0, col, 2)
            else:
                self.flash_msg = ""

        if self.show_help:
            self._draw_help(frame, color)

        cv2.putText(frame,
                    "[Q]Quit [M]Mode [H]Help [S]Screenshot [R]PPT",
                    (10, h-8), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (90,90,90), 1)
        return frame

    def _draw_help(self, frame, color):
        h, w = frame.shape[:2]
        tips = {
            "AUTO": [
                "VOLUME: Spread 5 fingers WIDE",
                "  Rotate CW=UP  CCW=DOWN",
                "  Spread->Fist hold 1s = Mute",
                "MOUSE: Index up = Move cursor",
                "  I+M pinch = Left click",
                "  T+I pinch = Right click",
                "  3 fingers up+down = Scroll",
            ],
            "SPOTIFY": [
                "Index swipe RIGHT = Next",
                "Index swipe LEFT  = Prev",
                "Index + Pinky UP  = Play/Pause",
            ],
            "POWERPOINT": [
                "2-finger swipe RIGHT = Next slide",
                "2-finger swipe LEFT  = Prev slide",
                "Open hand 0.5s = Start slideshow",
                "Fist hold 1s   = End slideshow",
            ],
        }
        lines = tips.get(self.mode, [])
        ph = 28 + len(lines) * 24 + 12
        px, py = w - 365, 68

        ovl = frame.copy()
        cv2.rectangle(ovl, (px, py), (px+350, py+ph), (10, 10, 15), -1)
        cv2.addWeighted(ovl, 0.80, frame, 0.20, 0, frame)
        cv2.rectangle(frame, (px, py), (px+350, py+ph), color, 2)
        cv2.putText(frame, f" {self.mode}", (px+6, py+20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        for i, line in enumerate(lines):
            cv2.putText(frame, f"  {line}",
                        (px+6, py+40+i*24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.44, (210,210,210), 1)

    def _draw_vol_dial(self, frame, angle):
        h, w = frame.shape[:2]
        cx, cy, r = w-90, h//2, 55
        cv2.circle(frame, (cx, cy), r, (30,30,30), -1)
        cv2.circle(frame, (cx, cy), r, (0,200,255), 2)
        vol_pct = self.volume.get_volume_pct()
        sweep = int(vol_pct * 3.6)
        cv2.ellipse(frame, (cx, cy), (r,r), -90, 0, sweep, (0,200,255), 5)
        if angle is not None:
            ax = int(cx + (r-10)*math.cos(math.radians(angle)))
            ay = int(cy + (r-10)*math.sin(math.radians(angle)))
            cv2.arrowedLine(frame, (cx,cy), (ax,ay), (255,255,255), 2, tipLength=0.35)
        cv2.putText(frame, f"{vol_pct}%",
                    (cx-18, cy+6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,200,255), 2)
        cv2.putText(frame, "CW=UP",
                    (cx-24, cy+r+18), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (120,120,120), 1)

    def _draw_hold_bar(self, frame, elapsed, total, label):
        h, w = frame.shape[:2]
        bx, by, bw, bh = 10, h-110, 300, 20
        pct = min(elapsed/total, 1.0)
        cv2.rectangle(frame, (bx, by), (bx+bw, by+bh), (40,40,40), -1)
        cv2.rectangle(frame, (bx, by), (int(bx+bw*pct), by+bh), (0,200,255), -1)
        cv2.rectangle(frame, (bx, by), (bx+bw, by+bh), (0,200,255), 1)
        cv2.putText(frame, label, (bx, by-6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,200,255), 1)

    def _flash(self, msg: str):
        self.flash_msg  = msg
        self.flash_time = time.time()
        print(f"[ACTION] {msg}")


# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = GestureApp()
    app.run()
