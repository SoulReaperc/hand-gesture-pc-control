# ✋ AI Hand Gesture PC Controller

> **Real-Time Machine Learning & Computer Vision Controller**  
> Python 3.12 | MediaPipe Tasks | Scikit-Learn | OpenCV | pycaw | PyAutoGUI | win32com

Control your entire PC hands-free using your webcam and custom-trained Deep MLP neural networks. Includes precision jitter-free mouse navigation, media controls, and PowerPoint presentation control.

---

## ⚡ Quick Command Reference

| Goal | Command | Description |
| :--- | :--- | :--- |
| **▶ Run Controller** | `python main.py` | Launches the webcam gesture controller with real-time HUD. |
| **🎥 Record Data** | `python collect_gesture_data.py` | Record your own hand gestures via webcam into `gesture_dataset_custom.csv`. |
| **🧠 Train Model** | `python train_gesture_model.py` | Trains the Deep MLP classifier and saves `gesture_model.joblib`. |
| **📊 Result Diagrams** | *Auto-generated in `model_results/`* | Confusion matrix, training loss curve, and per-class F1 graphs. |

---

## 🎮 Modes & Gesture Controls

Switch modes anytime by **holding the OK Gesture** (Thumb + Index pinched together with Middle, Ring, Pinky extended UP) for **0.45 seconds**.  
The modes cycle continuously:

$$\mathbf{CURSOR} \longrightarrow \mathbf{MEDIA} \longrightarrow \mathbf{PRESENTATION} \longrightarrow \mathbf{CURSOR}$$

---

### 1. 🖱️ `CURSOR` Mode (Mouse Control)

Engineered with **anatomical joint blending**, **6-pixel dead zone**, and **pre-click position freeze** to eliminate jitter and drift when clicking.

| Action | Hand Gesture | Notes |
| :--- | :--- | :--- |
| **Move Cursor** | Index finger pointing up | Smooth, velocity-adaptive pointer movement. |
| **Left Click** | Index + Middle fingertip pinch | Position is locked in place so clicks never drag. |
| **Right Click** | Thumb + Index fingertip pinch | Context menu trigger. |
| **Scroll Up/Down** | 3 fingers up (Index, Middle, Ring) | Move hand up or down to scroll web pages/documents. |
| **Cycle Mode** | Hold **OK Gesture** (0.45s) | Circular progress ring fills and cycles to MEDIA mode. |

---

### 2. 🎵 `MEDIA` Mode (Spotify, YouTube, Media Player)

| Action | Hand Gesture | Notes |
| :--- | :--- | :--- |
| **Volume Dial** | Spread all 5 fingers & rotate wrist | Clockwise = Volume UP, Counter-Clockwise = Volume DOWN. |
| **Mute / Unmute** | Fist (hold 1.0 second) | Circular progress bar fills to toggle mute. |
| **Next Track** | Index finger swipe **RIGHT** | Plays next video or song. |
| **Prev Track** | Index finger swipe **LEFT** | Plays previous video or song. |
| **Play / Pause** | "Rock On" / Horns gesture (Index + Pinky up) | Toggles playback. |
| **Cycle Mode** | Hold **OK Gesture** (0.45s) | Cycles to PRESENTATION mode. |

---

### 3. 📊 `PRESENTATION` Mode (PowerPoint, Google Slides, PDF)

Features automatic PowerPoint window activation and native Windows COM automation.

| Action | Hand Gesture | Trigger Behavior |
| :--- | :--- | :--- |
| **Next Slide** | **Point** (Index Finger Up) | Debounced with a 0.65s cooldown so holding doesn't rapid-skip. |
| **Previous Slide** | **Peace** (Two Fingers Up: V-Sign) | Goes back one slide cleanly. |
| **Start Slideshow** | **Pinch** (Thumb + Index pinched) | Hold pinch for 0.35s to start fullscreen slideshow (**F5**). |
| **End Slideshow** | **Thumbs Up** (👍 Vertical Thumb) | Hold thumbs up for 0.45s to exit slideshow (**Esc**). |
| **Cycle Mode** | Hold **OK Gesture** (0.45s) | Cycles to CURSOR mode. |

---

## 🎥 How to Record Your Own Hand Gestures

You can record custom real-world hand gestures directly from your webcam:

1. Run the interactive recorder:
   ```powershell
   python collect_gesture_data.py
   ```
2. Select which gesture to record using keys **`0` to `8`**:
   - `0`: NONE (Relaxed / background hand)
   - `1`: INDEX_POINT (Pointing up)
   - `2`: V_SIGN (Peace sign)
   - `3`: OPEN_PALM (5 fingers wide open)
   - `4`: FIST (Curled fist)
   - `5`: OK_GESTURE (Thumb + Index touching, 3 fingers up)
   - `6`: ROCK_HORNS (Index + Pinky up)
   - `7`: THUMBS_UP (👍 Vertical thumb)
   - `8`: PINCH (Thumb + Index tips touching)
3. **Capture data**:
   - Press **`SPACE`** to capture a single sample.
   - Press **`B`** to capture a burst of 50 samples with a 1-second countdown (tilt and move your hand slightly for variance).
4. **Save dataset**:
   - Press **`S`** to save into `gesture_dataset_custom.csv`.
   - Press **`Q`** to exit.

---

## 🧠 How to Train the Model & Generate Graphs

Once your dataset is ready (or using the built-in generator), train the neural network with a single command:

```powershell
python train_gesture_model.py
```

### What This Command Does:
1. Detects and loads `gesture_dataset_custom.csv` (or generates augmented geometric data if absent).
2. Extracts 78 scale- and translation-invariant geometric features.
3. Splits into 75% train and 25% test sets (stratified).
4. Trains a **Deep Multi-Layer Perceptron (MLP)** neural network (`128x64` ReLU architecture).
5. Evaluates classification performance (Accuracy, Precision, Recall, F1).
6. **Automatically saves publication-quality evaluation diagrams into `model_results/`**:
   - 📈 `model_results/confusion_matrix.png` — Heatmap of true vs. predicted classes.
   - 📉 `model_results/loss_curve.png` — Optimization loss curve showing neural convergence.
   - 📊 `model_results/f1_per_class.png` — Bar chart of per-gesture classification F1-scores.
7. Saves the champion model artifact: `gesture_model.joblib`.
8. Updates metadata metrics in `model_metadata.json`.

---

## 📈 Evaluation Results & Output Diagrams

All training output graphs and diagrams are saved in the [`model_results/`](model_results/) folder:

| Diagram | File Path | Description |
| :--- | :--- | :--- |
| **Confusion Matrix** | [`model_results/confusion_matrix.png`](model_results/confusion_matrix.png) | Multi-class prediction heatmap showing true positive rates across all gestures. |
| **Loss Curve** | [`model_results/loss_curve.png`](model_results/loss_curve.png) | Cross-entropy training loss vs. epoch iterations. |
| **F1-Score Chart** | [`model_results/f1_per_class.png`](model_results/f1_per_class.png) | Per-class accuracy comparison across all 9 classes. |

### Model Benchmark Summary:
- **Architecture**: Deep MLP Neural Network (`128 -> 64 -> Softmax`)
- **Test Accuracy**: **96.46%** (on real recorded hand data) / **100.00%** (on canonical geometric sets)
- **Weighted F1 Score**: **96.43%**
- **Inference Latency**: **0.29 ms** per frame (>3,400 FPS throughput on CPU)
- **Model Size**: ~455 KB (ultra-lightweight, zero cloud dependencies)

---

## 🛠️ Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/SoulReaperc/hand-gesture-pc-control.git
cd hand-gesture-pc-control
```

### 2. Create and activate a Python virtual environment
```powershell
python -m venv venv
.\venv\Scripts\activate
```

### 3. Install required packages
```powershell
pip install -r requirements.txt
```

### 4. Run the project
```powershell
python main.py
```

---

## ⌨️ In-App Hotkeys

While the camera feed window is active:

| Key | Function |
| :---: | :--- |
| **`H`** | Toggle on-screen gesture help card overlay |
| **`M`** | Manually cycle active mode (`CURSOR` $\rightarrow$ `MEDIA` $\rightarrow$ `PRESENTATION`) |
| **`T`** | Toggle ML inference mode (AI Neural Net vs. Heuristic) |
| **`S`** | Take a screenshot of the current camera frame |
| **`R`** | Reconnect to Microsoft PowerPoint COM session |
| **`Q`** / **`ESC`** | Exit application |

---

## 📂 Project Architecture

```
Gester_Control/
├── main.py                     # Main application loop, HUD & gesture routing
├── gesture_detector.py         # MediaPipe Tasks 3D hand tracking & heuristic detectors
├── ml_feature_extractor.py     # 78-dimensional invariant geometric feature extractor
├── ml_gesture_classifier.py    # Runtime neural net inference with probability smoothing
├── collect_gesture_data.py     # Interactive webcam dataset recording utility
├── train_gesture_model.py      # Production MLP trainer & evaluation graph generator
├── gesture_model.joblib        # Serialized champion neural network model
├── model_metadata.json         # Benchmark metrics and active class mappings
│
├── mouse_control.py            # Precision mouse pointer & click operations
├── volume_control.py           # Core Audio volume & mute controller (pycaw)
├── spotify_control.py          # Spotify playback controller (API / media keys)
├── powerpoint_control.py       # PowerPoint slide controller (win32com / window focus)
│
├── model_results/              # Output charts, diagrams, and evaluation graphs
│   ├── confusion_matrix.png
│   ├── loss_curve.png
│   └── f1_per_class.png
│
├── gesture_dataset_custom.csv  # Your recorded custom hand landmark samples
├── requirements.txt            # Project dependencies
└── README.md                   # Comprehensive project documentation
```

---

*College ML Project — Built with Python 3.12, MediaPipe & Scikit-Learn.*
