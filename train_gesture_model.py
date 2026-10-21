"""
Production Hand Gesture Model Trainer
=====================================
Trains the champion Deep MLP (Multi-Layer Perceptron) gesture classifier.
Can train from:
  1. `gesture_dataset_custom.csv` if generated using `collect_gesture_data.py`
  2. Built-in geometric hand model generator (with realistic hand articulation noise,
     rotation, scale, and camera jitter augmentation).

Outputs:
  - `gesture_model.joblib`: Trained model + standard scaler ready for real-time inference.
  - `model_metadata.json`: Model benchmark metrics & classes.
"""

import os
import json
import numpy as np
import pandas as pd
import joblib
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, f1_score
from ml_feature_extractor import extract_ml_features, FEATURE_NAMES

CLASSES = [
    "Neutral",
    "Index Point",
    "Pinch Click",
    "Thumb Pinch",
    "Three Fin Scroll",
    "Open Spread",
    "Fist Hold",
    "Horns Rock",
    "Peace Two Fin"
]

def synthesize_hand_landmarks(gesture_idx, num_samples=350):
    """
    Generates realistic 21 hand landmarks (x, y, z) for 9 gesture classes
    with rotational, scale, and sensor noise augmentation.
    """
    base_wrist = np.array([320.0, 400.0, 0.0])
    samples = []

    for _ in range(num_samples):
        scale = np.random.uniform(0.75, 1.25)
        angle = np.random.uniform(-0.35, 0.35)  # rotation in radians
        cos_a, sin_a = np.cos(angle), np.sin(angle)
        R = np.array([[cos_a, -sin_a], [sin_a, cos_a]])

        lms = np.zeros((21, 3))
        lms[0] = base_wrist + np.random.normal(0, 10, 3)

        # Approximate base MCP joints relative to wrist
        mcp_offsets = [
            [-35, -50, 0],   # Thumb MCP (1)
            [-25, -120, 0],  # Index MCP (5)
            [0, -130, 0],    # Middle MCP (9)
            [25, -120, 0],   # Ring MCP (13)
            [45, -100, 0]    # Pinky MCP (17)
        ]

        # Finger extension states per gesture
        # [Thumb, Index, Middle, Ring, Pinky]
        states = {
            0: [0.5, 0.5, 0.5, 0.5, 0.5], # Neutral relaxed
            1: [0.2, 1.0, 0.1, 0.1, 0.1], # Index Point
            2: [0.3, 0.6, 0.6, 0.1, 0.1], # Pinch Click (Index+Middle tips touching)
            3: [0.6, 0.6, 0.9, 0.9, 0.9], # Thumb Pinch (OK sign)
            4: [0.2, 1.0, 1.0, 1.0, 0.1], # Three Fin Scroll
            5: [1.0, 1.0, 1.0, 1.0, 1.0], # Open Spread
            6: [0.1, 0.1, 0.1, 0.1, 0.1], # Fist Hold
            7: [0.2, 1.0, 0.1, 0.1, 1.0], # Horns Rock
            8: [0.2, 1.0, 1.0, 0.1, 0.1], # Peace Two Fin
        }

        ext = states.get(gesture_idx, [0.5]*5)

        # Generate 21 landmarks
        for f_idx, (mcp_off, is_ext) in enumerate(zip(mcp_offsets, ext)):
            mcp_id = [1, 5, 9, 13, 17][f_idx]
            mcp_pos = lms[0] + np.array(mcp_off) * scale
            lms[mcp_id] = mcp_pos

            bone_len = (25.0 if f_idx == 0 else 32.0) * scale

            for step in range(1, 4):
                curr_id = mcp_id + step
                prev_pos = lms[curr_id - 1]

                if f_idx == 0:  # Thumb direction
                    dir_vec = np.array([-1.0, -1.0, 0.0]) if is_ext > 0.5 else np.array([0.5, -0.5, 0.0])
                else:  # Other fingers
                    if is_ext > 0.7:  # Extended upwards
                        dir_vec = np.array([0.0, -1.0, 0.0])
                    elif is_ext > 0.4:  # Half curled
                        dir_vec = np.array([0.0, -0.5, 0.5])
                    else:  # Curled into palm
                        dir_vec = np.array([0.0, 0.6, 0.4])

                dir_norm = dir_vec / (np.linalg.norm(dir_vec) + 1e-6)
                pos = prev_pos + dir_norm * bone_len + np.random.normal(0, 2.5, 3)
                lms[curr_id] = pos

        # Apply 2D rotation to x, y
        xy = lms[:, :2] - base_wrist[:2]
        lms[:, :2] = (xy @ R.T) + base_wrist[:2]
        # Add slight camera depth jitter
        lms[:, 2] += np.random.normal(0, 3.0, 21)

        # Convert to lm_list format: [[id, x, y, z], ...]
        lm_formatted = [[i, int(lms[i, 0]), int(lms[i, 1]), float(lms[i, 2])] for i in range(21)]
        feat = extract_ml_features(lm_formatted)
        if feat is not None:
            samples.append(feat)

    return np.array(samples)

def load_or_generate_dataset():
    """Loads custom CSV if available, otherwise generates augmented synthetic dataset."""
    custom_csv = "gesture_dataset_custom.csv"
    if os.path.exists(custom_csv):
        print(f" Loading custom collected dataset from '{custom_csv}'...")
        df = pd.read_csv(custom_csv)
        feature_cols = [c for c in df.columns if c not in ["label_id", "label_name"]]
        X = df[feature_cols].values
        y = df["label_id"].values
        label_df = df[["label_id", "label_name"]].drop_duplicates().sort_values("label_id")
        class_names = [row["label_name"] for _, row in label_df.iterrows()]
        return X, y, class_names

    print("Generating comprehensive geometric hand dataset across 9 gestures with augmentation...")
    X_list, y_list = [], []
    for g_idx in range(len(CLASSES)):
        feats = synthesize_hand_landmarks(g_idx, num_samples=400)
        X_list.append(feats)
        y_list.append(np.full(len(feats), g_idx, dtype=int))

    X = np.vstack(X_list)
    y = np.concatenate(y_list)
    return X, y, CLASSES


def generate_evaluation_diagrams(y_test, y_pred, mlp_model, class_names, output_dir="model_results"):
    """Generates and saves publication-quality evaluation diagrams and charts."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

    os.makedirs(output_dir, exist_ok=True)
    plt.style.use("dark_background")

    # ── 1. Confusion Matrix Heatmap ──────────────────────────────────
    cm = confusion_matrix(y_test, y_pred)
    fig, ax = plt.subplots(figsize=(9, 8), dpi=200)
    cax = ax.matshow(cm, cmap="Blues", alpha=0.85)
    fig.colorbar(cax, fraction=0.046, pad=0.04)

    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            val = cm[i, j]
            color = "white" if val > cm.max() / 2 else "#aaaaaa"
            ax.text(j, i, str(val), ha="center", va="center", color=color, fontweight="bold", fontsize=11)

    labels = [class_names[i] if i < len(class_names) else f"C{i}" for i in range(len(cm))]
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="left", fontsize=9)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Predicted Gesture", fontsize=12, labelpad=12, color="#00ffcc")
    ax.set_ylabel("True Gesture", fontsize=12, labelpad=12, color="#00ffcc")
    ax.set_title("Hand Gesture Recognition — Confusion Matrix", fontsize=14, pad=20, fontweight="bold", color="#ffffff")
    plt.tight_layout()
    cm_path = os.path.join(output_dir, "confusion_matrix.png")
    fig.savefig(cm_path, bbox_inches="tight")
    plt.close(fig)
    print(f" Saved confusion matrix diagram: {cm_path}")

    # ── 2. Training Loss Curve ───────────────────────────────────────
    if hasattr(mlp_model, "loss_curve_"):
        fig, ax = plt.subplots(figsize=(8, 5), dpi=200)
        ax.plot(mlp_model.loss_curve_, color="#00ffff", linewidth=2.5, label="MLP Loss (Cross-Entropy)")
        ax.fill_between(range(len(mlp_model.loss_curve_)), mlp_model.loss_curve_, color="#00ffff", alpha=0.15)
        ax.set_title("Deep MLP Neural Network — Training Loss Curve", fontsize=13, fontweight="bold", pad=15)
        ax.set_xlabel("Epoch / Iteration", fontsize=11)
        ax.set_ylabel("Loss", fontsize=11)
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.legend(loc="upper right", frameon=True)
        plt.tight_layout()
        loss_path = os.path.join(output_dir, "loss_curve.png")
        fig.savefig(loss_path, bbox_inches="tight")
        plt.close(fig)
        print(f" Saved training loss curve graph: {loss_path}")

    # ── 3. Per-Class F1 Score Bar Chart ──────────────────────────────
    prec, rec, f1_vals, _ = precision_recall_fscore_support(y_test, y_pred, zero_division=0)
    fig, ax = plt.subplots(figsize=(10, 5), dpi=200)
    x_indices = np.arange(len(labels))
    bars = ax.bar(x_indices, f1_vals * 100, color="#20b2aa", width=0.55, edgecolor="#00ffcc", linewidth=1.5)

    for bar, val in zip(bars, f1_vals * 100):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.2, f"{val:.1f}%",
                ha="center", va="bottom", fontsize=9, fontweight="bold", color="#ffffff")

    ax.set_ylim(0, 115)
    ax.set_xticks(x_indices)
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("F1 Score (%)", fontsize=11)
    ax.set_title("Per-Class Classification Accuracy (F1-Score)", fontsize=13, fontweight="bold", pad=15)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    plt.tight_layout()
    f1_path = os.path.join(output_dir, "f1_per_class.png")
    fig.savefig(f1_path, bbox_inches="tight")
    plt.close(fig)
    print(f" Saved per-class performance chart: {f1_path}")


def main():
    print("=" * 65)
    print("      HAND GESTURE CLASSIFIER - CHAMPION MODEL TRAINER")
    print("=" * 65)

    X, y, class_names = load_or_generate_dataset()
    print(f"Dataset shape: {X.shape[0]} samples, {X.shape[1]} invariant features.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    print(f"Training set: {X_train.shape[0]} samples | Test set: {X_test.shape[0]} samples")

    # Pipeline: StandardScaler + Deep MLP Classifier
    # 128x64 layers provides sub-millisecond forward pass & high non-linear expressiveness
    mlp_classifier = MLPClassifier(
        hidden_layer_sizes=(128, 64),
        activation="relu",
        solver="adam",
        alpha=0.0001,
        max_iter=350,
        random_state=42,
        early_stopping=True,
        n_iter_no_change=15
    )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("mlp", mlp_classifier)
    ])

    print("\nTraining Deep MLP Neural Network...")
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average="weighted")

    print("\n" + "=" * 65)
    print(f"  MODEL TRAINING COMPLETE!")
    print(f"  Test Accuracy : {acc * 100:.2f}%")
    print(f"  Weighted F1   : {f1 * 100:.2f}%")
    print("=" * 65)
    print("\nClassification Report:\n")
    target_names = [class_names[i] if i < len(class_names) else f"Class_{i}" for i in sorted(np.unique(y_test))]
    print(classification_report(y_test, y_pred, target_names=target_names))

    # Generate evaluation diagrams and graphs
    print("\nGenerating model result charts and diagrams...")
    generate_evaluation_diagrams(y_test, y_pred, pipeline.named_steps["mlp"], class_names)

    # Save artifact
    model_path = "gesture_model.joblib"
    joblib.dump(pipeline, model_path)
    file_size_kb = os.path.getsize(model_path) / 1024
    print(f"\n Saved champion model to '{model_path}' ({file_size_kb:.1f} KB)")

    # Save metadata
    metadata = {
        "model_name": "Deep MLP Neural Network Gesture Classifier",
        "champion_architecture": "MLP (128x64 ReLU, Softmax Output)",
        "classes": class_names,
        "n_classes": len(class_names),
        "n_features": X.shape[1],
        "test_accuracy": float(acc),
        "test_f1": float(f1),
        "trained_on_custom": os.path.exists("gesture_dataset_custom.csv"),
    }
    with open("model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(" Updated 'model_metadata.json'")

if __name__ == "__main__":
    main()
