# ✋ Gesture Control System

> **College ML Project** | Python 3.12 | MediaPipe | OpenCV | pycaw | pyautogui | win32com

A real-time hand-gesture control system using a webcam and MediaPipe hand tracking. Control your computer — volume, mouse, Spotify, and PowerPoint — entirely with hand gestures, no touch required.

---

## 🚀 Features

| Feature | Gestures |
|---|---|
| 🔊 **System Volume** | Thumb + Index pinch distance |
| 🖱️ **Mouse Move** | Index finger only |
| 🖱️ **Left Click** | Index + Middle tips close together |
| 🖱️ **Double Click** | 3 fingers close together |
| 🖱️ **Right Click** | Pinky finger only |
| 🖱️ **Scroll** | Fist moving up / down |
| 🎵 **Spotify Next** | Swipe right (index finger) |
| 🎵 **Spotify Prev** | Swipe left (index finger) |
| 🎵 **Spotify Play/Pause** | Thumb up |
| 📊 **PPT Next Slide** | Swipe right (index + middle) |
| 📊 **PPT Prev Slide** | Swipe left (index + middle) |
| 📊 **Start Slideshow** | Open hand (5 fingers) |
| 📊 **End Slideshow** | Fist (hold 1 second) |
| 🔇 **Mute Toggle** | Fist hold 1 second (Volume mode) |

---

## 📁 Project Structure

```
Gester_Control/
│
├── main.py                 # Main app — mode switching, HUD, orchestration
├── gesture_detector.py     # MediaPipe hand detection + helpers
├── volume_control.py       # System volume via pycaw (Windows Core Audio)
├── mouse_control.py        # Mouse move/click/scroll via pyautogui
├── spotify_control.py      # Spotify next/prev/play via API or media keys
├── powerpoint_control.py   # PPT slide nav via win32com or keyboard
│
├── requirements.txt
├── .env.example            # Copy to .env and add Spotify credentials
└── README.md
```

---

## ⚙️ Setup

### 1. Create & activate virtual environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. (Optional) Spotify API credentials
```bash
# Copy .env.example → .env and fill in:
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```
> Without credentials, the app automatically falls back to keyboard media keys.

---

## Run

```bash
python main.py
```

---

## 🎮 Keyboard Shortcuts (while window is focused)

| Key | Action |
|-----|--------|
| Q or Esc | Quit |
| M | Cycle mode: AUTO → VOLUME → MOUSE → SPOTIFY → POWERPOINT |
| H | Toggle help overlay |
| S | Save screenshot |
| R | Reconnect PowerPoint COM automation |

---

## Gesture Reference

### VOLUME mode
| Gesture | Action |
|---|---|
| Thumb+Index distance | Volume 0-100% |
| Fist (hold 1s) | Mute/Unmute |

### MOUSE mode
| Gesture | Action |
|---|---|
| Index only | Move cursor |
| Index + Middle (close) | Left click |
| 3 fingers (close) | Double click |
| Pinky only | Right click |
| Fist / move up/down | Scroll |

### SPOTIFY mode
| Gesture | Action |
|---|---|
| Swipe right (index) | Next track |
| Swipe left (index) | Previous track |
| Thumb up | Play / Pause |

### POWERPOINT mode
| Gesture | Action |
|---|---|
| Swipe right (2 fingers) | Next slide |
| Swipe left (2 fingers) | Previous slide |
| Open hand (5 fingers) | Start slideshow |
| Fist hold 1s | End slideshow |

---

## How It Works

1. **Capture**: OpenCV reads webcam frames in real-time.
2. **Detect**: MediaPipe Hands detects 21 3D landmarks per hand.
3. **Interpret**: GestureDetector extracts finger states, distances, and gesture names.
4. **Act**: Mode handler routes gesture to the appropriate controller.
5. **Overlay**: HUD drawn live with mode badge, FPS, gesture name, finger indicators.

---

## Dependencies

| Package | Purpose |
|---|---|
| mediapipe | Hand landmark detection |
| opencv-python | Camera capture & frame rendering |
| pycaw | Windows Core Audio volume API |
| pyautogui | Mouse/keyboard automation |
| pywin32 | COM automation for PowerPoint |
| spotipy | Spotify Web API |
| python-dotenv | .env file loading |
| numpy | Numeric interpolation |

---

*Made for college ML project presentation*
