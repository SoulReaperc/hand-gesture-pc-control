"""
volume_control.py
─────────────────
System volume control via pycaw (new API: pycaw >= 2026).
Uses AudioDevice.EndpointVolume directly.

Gesture:  Thumb + Index pinch distance  →  0–100 % volume
          Fist hold 1 s                 →  Mute / Unmute
"""

import numpy as np
from pycaw.pycaw import AudioUtilities


class VolumeController:
    """Controls Windows master volume via hand pinch gesture."""

    MIN_DIST = 20    # pixel distance → 0 % volume
    MAX_DIST = 200   # pixel distance → 100 % volume

    def __init__(self):
        device = AudioUtilities.GetSpeakers()
        # New pycaw (≥2026): AudioDevice.EndpointVolume is the COM interface
        self._volume = device.EndpointVolume
        vol_range = self._volume.GetVolumeRange()   # (min_dB, max_dB, step_dB)
        self._min_vol = vol_range[0]
        self._max_vol = vol_range[1]

    # ─── public ───────────────────────────────────────────────────────

    def set_from_distance(self, dist: float) -> int:
        """
        Convert pixel *dist* to volume level and apply it.
        Returns the new volume percentage (0-100).
        """
        vol_pct = self._dist_to_pct(dist)
        self._set_volume_pct(vol_pct)
        return vol_pct

    def get_volume_pct(self) -> int:
        """Return current system volume as integer 0-100."""
        return round(self._volume.GetMasterVolumeLevelScalar() * 100)

    def mute(self):
        self._volume.SetMute(1, None)

    def unmute(self):
        self._volume.SetMute(0, None)

    def toggle_mute(self):
        state = self._volume.GetMute()
        self._volume.SetMute(not state, None)

    # ─── private ──────────────────────────────────────────────────────

    def _dist_to_pct(self, dist: float) -> int:
        pct = np.interp(dist, [self.MIN_DIST, self.MAX_DIST], [0, 100])
        return int(np.clip(pct, 0, 100))

    def set_volume_pct(self, pct: int):
        """Set volume to a specific percentage (0-100)."""
        scalar = pct / 100.0
        self._volume.SetMasterVolumeLevelScalar(scalar, None)

    # Keep private alias for backward compat
    _set_volume_pct = set_volume_pct
