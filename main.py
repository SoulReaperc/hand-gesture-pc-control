"""
main.py  ─  Gesture Control System
════════════════════════════════════════════════════════════════════════
Python 3.12 | MediaPipe Tasks 1.0 | OpenCV | pycaw | pyautogui | win32com

Run:  python main.py
Keys: Q/Esc=quit  M=next mode  T=toggle AI ML  H=help  S=screenshot  R=PPT reconnect

════════════════════════════════════════════════════════════════════════
GESTURE & MODE REFERENCE
─────────────────────────────────────────────────────────────────────
▶ OK GESTURE (Works Anywhere):
    Thumb + Index tips pinch with 3 fingers UP → Hold 0.4s to cycle mode:
    CURSOR → MEDIA → PRESENTATION → CURSOR

▶ CURSOR MODE
    Index finger pointing (only)  → Move cursor (Dead Zone & Anti-Jitter)
    Index + Middle tips PINCH     → Left Click (Cursor locks in place!)
    Thumb + Index tips PINCH      → Right Click (Cursor locks in place!)
    3 fingers up + move hand dy   → Smooth Scroll UP / DOWN

▶ MEDIA MODE
    All 5 fingers spread & rotate → System Volume (CW = UP, CCW = DOWN)
    Spread-open → close to FIST   → Hold 1s = Mute toggle
    Index swipe RIGHT             → Next Track / Next Video
    Index swipe LEFT              → Prev Track / Prev Video
    Peace (2 fingers) or Horns    → Play / Pause

▶ PRESENTATION MODE
    Index pointing / swipe RIGHT  → Next Slide (PowerPoint / Slides)
    Index swipe LEFT              → Previous Slide
    Open Hand (5 fingers)         → Hold 0.5s = Start Slideshow (F5)
    Fist                          → Hold 0.8s = End Slideshow (Esc)
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

MODES = ["CURSOR", "MEDIA", "PRESENTATION"]
MODE_COLORS = {
    "CURSOR":       (255, 200,  50),  # Electric Cyan / Yellow
    "MEDIA":        ( 80, 255, 100),  # Media Green
    "PRESENTATION": ( 50, 140, 255),  # Slide Orange
}

# Volume
SPREAD_MIN_PX  = 160   # min thumb-tip to pinky-tip distance to count as "spread"
ROT_STEP_DEG   = 18    # degrees per volume step
VOL_STEP_PCT   = 2     # % per step
ROT_DEAD_DEG   = 5     # ignore jitter below this

# Mouse / Cursor Sensitivity & Dead Zone Configuration
DEAD_ZONE_PX   = 6.0   # Screen pixel dead zone (eliminates hand tremor micro-jitter)
MOUSE_MARGIN_X = 0.30  # Active central tracking region (horizontal)
MOUSE_MARGIN_Y = 0.28  # Active central tracking region (vertical)
MOUSE_SMOOTH_SLOW = 5.0  # High smoothing factor when moving slowly / hovering
MOUSE_SMOOTH_FAST = 2.0  # Responsive low smoothing when moving fast
CLICK_COOL     = 0.40  # Seconds between click triggers
SCROLL_COOL    = 0.10  # Seconds between scroll actions

# Mode Switch
OK_HOLD_SEC    = 0.45  # Seconds to hold OK gesture to cycle mode
OK_COOLDOWN    = 1.20  # Cooldown seconds between mode switches

# Swipe
SWIPE_WIN      = 12
SWIPE_PX       = 75

# Holds
FIST_HOLD      = 0.85
OPEN_HOLD      = 0.50


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
        self._freeze_cursor_until = 0.0  # Lock cursor during click/pinch to prevent drifting

        # ── Mode Switch & OK Gesture state ────────────────────────
        self._ok_start_t          = None
        self._last_mode_switch_t  = 0.0

        # ── Swipe / Spotify / PPT state ───────────────────────────
        self._swipe_x          : list[int] = []
        self._last_spotify_pp  = 0.0
        self._open_t           = None
        self._ppt_fist_t       = None
        self._ppt_last_nav_t   = 0.0
        self._ppt_pinch_start  = None
        self._ppt_thumb_start  = None
        self._ppt_point_start  = None
        self._ppt_peace_start  = None

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
                    # ── OK Hand Gesture Mode Switch (Global) ──────────
                    now = time.time()
                    if self.detector.is_ok_gesture():
                        if self._ok_start_t is None:
                            self._ok_start_t = now
                        elapsed_ok = now - self._ok_start_t
                        next_idx = (self.mode_idx + 1) % len(MODES)
                        self._draw_hold_bar(frame, elapsed_ok, OK_HOLD_SEC, f"OK Gesture: Switch to {MODES[next_idx]}")
                        if elapsed_ok >= OK_HOLD_SEC and (now - self._last_mode_switch_t > OK_COOLDOWN):
                            self.mode_idx = next_idx
                            self.mode = MODES[self.mode_idx]
                            self._last_mode_switch_t = now
                            self._ok_start_t = None
                            self._reset_vol()
                            self._swipe_x.clear()
                            self._flash(f"MODE → {self.mode}")
                    else:
                        self._ok_start_t = None

                    # Execute actions for active mode when not cycling
                    if self._ok_start_t is None:
                        if   self.mode == "CURSOR":       self._cursor_mode(frame, fingers, lm)
                        elif self.mode == "MEDIA":        self._media_mode(frame, fingers, lm)
                        elif self.mode == "PRESENTATION": self._presentation_mode(frame, fingers, lm)
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
            elif key == ord('t'):
                self.detector.use_ml = not self.detector.use_ml
                st = "AI MODEL: ENABLED" if self.detector.use_ml else "AI MODEL: DISABLED (Heuristics)"
                self._flash(st)
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
    # CURSOR MODE  — jitter-free mouse, click freeze & smooth scrolling
    # ══════════════════════════════════════════════════════════════════
    def _cursor_mode(self, frame, fingers, lm):
        T, I, M, R, P = fingers
        three_up  = (not T) and I and M and R and (not P)   # [0,1,1,1,0]
        now       = time.time()

        palm_size       = self.detector.get_palm_size()
        click_threshold = max(20.0, palm_size * 0.35)

        # ── Left Click: Index + Middle tips pinch ─────────────────────
        left_pinching = False
        if I and M and not R and not P:
            d, frame, info = self.detector.distance(8, 12, frame, draw=True)
            self._draw_pinch_dot(frame, info, d, click_threshold, green=True)
            if d < click_threshold:
                left_pinching = True
                self._freeze_cursor_until = now + 0.35  # Freeze cursor firmly
                if now - self._last_lclick > CLICK_COOL:
                    pyautogui.click()
                    self._last_lclick = now
                    self._flash("Left Click ✓")
            elif d < click_threshold * 1.30:
                # Approaching click: freeze cursor immediately to prevent drift
                self._freeze_cursor_until = now + 0.15
                left_pinching = True

        # ── Right Click: Thumb + Index tips pinch ─────────────────────
        right_pinching = False
        if T and I and not M and not R and not P:
            d, frame, info = self.detector.distance(4, 8, frame, draw=True)
            self._draw_pinch_dot(frame, info, d, click_threshold, green=False)
            if d < click_threshold:
                right_pinching = True
                self._freeze_cursor_until = now + 0.35  # Freeze cursor firmly
                if now - self._last_rclick > CLICK_COOL:
                    pyautogui.rightClick()
                    self._last_rclick = now
                    self._flash("Right Click ✓")
            elif d < click_threshold * 1.30:
                self._freeze_cursor_until = now + 0.15
                right_pinching = True

        # ── Scroll: 3 fingers up + hand moving up/down ────────────────
        if three_up:
            self._freeze_cursor_until = now + 0.20
            self._do_scroll(frame, lm, three_up=True)
        else:
            self._scroll_prev_y = None

        # ── Move Cursor (Index pointing, only when NOT pinching/clicking) ──
        if I and not R and not P and not three_up and not left_pinching and not right_pinching:
            if now >= self._freeze_cursor_until:
                self._do_mouse_move(frame, lm)

        # Guide
        h, w = frame.shape[:2]
        cv2.putText(frame,
                    "Index=Move | I+M Pinch=LClick | T+I Pinch=RClick | 3-Fingers=Scroll | Hold OK=Mode",
                    (10, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 200, 50), 1)

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
        # Blend Index Tip (lm 8) with Index PIP (lm 6) for jitter-resistant tracking
        ix = (lm[8][1] * 0.70 + lm[6][1] * 0.30)
        iy = (lm[8][2] * 0.70 + lm[6][2] * 0.30)

        mx = MOUSE_MARGIN_X
        my = MOUSE_MARGIN_Y
        tx = np.interp(ix, [int(CAM_W * mx), int(CAM_W * (1 - mx))], [0, sw - 1])
        ty = np.interp(iy, [int(CAM_H * my), int(CAM_H * (1 - my))], [0, sh - 1])
        tx = float(np.clip(tx, 0, sw - 1))
        ty = float(np.clip(ty, 0, sh - 1))

        # Dead Zone Calculation (ignore micro-tremors below DEAD_ZONE_PX)
        dx = tx - self._mx
        dy = ty - self._my
        delta_dist = math.hypot(dx, dy)

        if delta_dist < DEAD_ZONE_PX:
            cv2.circle(frame, (int(lm[8][1]), int(lm[8][2])), 8, (100, 255, 100), 1)
            return

        # Adaptive Velocity Smoothing (One-Euro style)
        if delta_dist < 18.0:
            smooth = MOUSE_SMOOTH_SLOW
        elif delta_dist > 60.0:
            smooth = MOUSE_SMOOTH_FAST
        else:
            t = (delta_dist - 18.0) / 42.0
            smooth = MOUSE_SMOOTH_SLOW * (1.0 - t) + MOUSE_SMOOTH_FAST * t

        self._mx += dx / smooth
        self._my += dy / smooth
        pyautogui.moveTo(int(round(self._mx)), int(round(self._my)))
        cv2.circle(frame, (int(lm[8][1]), int(lm[8][2])), 14, (50, 255, 130), cv2.FILLED)
        cv2.circle(frame, (int(lm[8][1]), int(lm[8][2])), 14, (0, 0, 0), 1)

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
    # MEDIA MODE  — Volume, Spotify & YouTube playback control
    # ══════════════════════════════════════════════════════════════════
    def _media_mode(self, frame, fingers, lm):
        T, I, M, R, P = fingers
        fist      = not any(fingers)
        is_spread = self._is_spread_open(fingers, lm)
        now       = time.time()
        ix        = lm[8][1]
        palm_size = self.detector.get_palm_size()
        swipe_threshold = max(35.0, palm_size * 0.50)

        # ── 1. Rotary Volume Dial & Spread->Fist Mute Sequence ───────
        self._do_volume(frame, fingers, lm, fist, is_spread)
        if is_spread or self._mute_holding or (now < self._mute_cooldown) or (now - self._last_spread_t < 0.8):
            return

        # ── 2. Play / Pause: Peace (2 fingers) OR Horns (Index+Pinky) ──
        peace_or_horns = (I and M and not R and not P) or (I and P and not T and not M and not R)
        if peace_or_horns:
            if now - self._last_spotify_pp > 0.70:
                self.spotify.play_pause()
                pyautogui.press('playpause')
                self._flash("⏯  Play / Pause")
                self._last_spotify_pp = now
            self._swipe_x.clear()
            return

        # ── 3. Next / Prev Track (Swipe Index) ───────────────────────
        if I and not M and not R and not P:
            self._swipe_x.append(ix)
            if len(self._swipe_x) > SWIPE_WIN:
                self._swipe_x.pop(0)
            if len(self._swipe_x) == SWIPE_WIN:
                dx = self._swipe_x[-1] - self._swipe_x[0]
                if dx > swipe_threshold:
                    self.spotify.next_track()
                    pyautogui.hotkey('shift', 'n')
                    pyautogui.press('nexttrack')
                    self._flash("⏭  Next Track / Video")
                    self._swipe_x.clear()
                elif dx < -swipe_threshold:
                    self.spotify.previous_track()
                    pyautogui.hotkey('shift', 'p')
                    pyautogui.press('prevtrack')
                    self._flash("⏮  Previous Track / Video")
                    self._swipe_x.clear()
        else:
            self._swipe_x.clear()

        h, w = frame.shape[:2]
        cv2.putText(frame,
                    "Spread Hand=Vol Dial | Peace/Horns=Play/Pause | Swipe=Next/Prev | Hold OK=Mode",
                    (10, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (80, 255, 100), 1)

    # ══════════════════════════════════════════════════════════════════
    # PRESENTATION MODE — PowerPoint, Google Slides & PDF presenter
    # ══════════════════════════════════════════════════════════════════
    def _presentation_mode(self, frame, fingers, lm):
        T, I, M, R, P = fingers
        now = time.time()

        is_pinch = self.detector.is_pinch(max_pinch_ratio=0.38)
        is_thumbs_up = self.detector.is_thumbs_up()
        is_point = I and (not M) and (not R) and (not P) and (not is_pinch)
        is_peace = I and M and (not R) and (not P) and (not is_pinch)

        # ── 1. Start Slideshow: Pinch (Thumb + Index) hold 0.35s ─────
        if is_pinch:
            if self._ppt_pinch_start is None:
                self._ppt_pinch_start = now
            e = now - self._ppt_pinch_start
            self._draw_hold_bar(frame, e, 0.35, "Hold Pinch → Start Slideshow (F5)")
            if e >= 0.35:
                self.ppt.start_slideshow()
                self._flash("PPT: Slideshow Started ▶ (F5)")
                self._ppt_pinch_start = None
                self._ppt_last_nav_t = now + 0.3
            return
        else:
            self._ppt_pinch_start = None

        # ── 2. End Slideshow: Thumbs Up hold 0.45s ───────────────────
        if is_thumbs_up:
            if self._ppt_thumb_start is None:
                self._ppt_thumb_start = now
            e = now - self._ppt_thumb_start
            self._draw_hold_bar(frame, e, 0.45, "Hold Thumbs Up → End Slideshow (Esc)")
            if e >= 0.45:
                self.ppt.end_slideshow()
                self._flash("PPT: Slideshow Ended ■ (Esc)")
                self._ppt_thumb_start = None
                self._ppt_last_nav_t = now + 0.3
            return
        else:
            self._ppt_thumb_start = None

        # ── 3. Next Slide: Point gesture (Index finger up) ────────────
        if is_point:
            if self._ppt_point_start is None:
                self._ppt_point_start = now
            e = now - self._ppt_point_start
            if e >= 0.18 and (now - self._ppt_last_nav_t > 0.65):
                self.ppt.next_slide()
                self._flash("▶ Next Slide (Point)")
                self._ppt_last_nav_t = now
        else:
            self._ppt_point_start = None

        # ── 4. Previous Slide: Peace gesture (Two fingers up) ─────────
        if is_peace:
            if self._ppt_peace_start is None:
                self._ppt_peace_start = now
            e = now - self._ppt_peace_start
            if e >= 0.18 and (now - self._ppt_last_nav_t > 0.65):
                self.ppt.previous_slide()
                self._flash("◀ Previous Slide (Peace)")
                self._ppt_last_nav_t = now
        else:
            self._ppt_peace_start = None

        info = self.ppt.current_slide_info()
        h, w = frame.shape[:2]
        if info:
            cv2.putText(frame, info, (10, h - 75),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (50, 140, 255), 2)
        cv2.putText(frame,
                    "Point=Next Slide | Peace=Prev Slide | Pinch=Start (F5) | Thumbs Up=End (Esc) | Hold OK=Mode",
                    (10, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (50, 140, 255), 1)

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
                    "[Q]Quit [M]Mode [T]AI Toggle [H]Help [S]Screenshot [R]PPT",
                    (10, h-8), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (90,90,90), 1)
        return frame

    def _draw_help(self, frame, color):
        h, w = frame.shape[:2]
        tips = {
            "CURSOR": [
                "OK Gesture (Thumb+Index) = Cycle Mode",
                "Index up = Move cursor (dead-zone smoothed)",
                "I+M pinch = Left click (pos locked)",
                "T+I pinch = Right click",
                "3 fingers (I+M+R) up/down = Scroll",
                "T+I drag hold = Drag & Drop",
            ],
            "MEDIA": [
                "OK Gesture (Thumb+Index) = Cycle Mode",
                "Index swipe RIGHT = Next track",
                "Index swipe LEFT  = Prev track",
                "Index + Pinky UP  = Play / Pause",
                "Spread 5 fingers & Rotate = Vol Up/Down",
                "Fist hold 1s      = Mute toggle",
            ],
            "PRESENTATION": [
                "OK Gesture (Hold) = Cycle Mode",
                "Point (Index Up)  = Next slide (→)",
                "Peace (Two Up)    = Previous slide (←)",
                "Pinch (T+I hold)  = Start slideshow (F5)",
                "Thumbs Up hold    = End slideshow (Esc)",
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
