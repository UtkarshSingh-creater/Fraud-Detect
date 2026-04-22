# ─────────────────────────────────────────────────────
# ml_models/train_temporal.py
# Generates synthetic training data and trains the LSTM
# Run: python ml_models/train_temporal.py
# Output: ml_models/weights/temporal_lstm.pth
# ─────────────────────────────────────────────────────

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from ml_models.temporal_analyzer import SuspiciousPatternLSTM, EVENT_TYPE_MAP

# ── Config ───────────────────────────────────────────
WINDOW_SIZE      = 60       # events per sequence
NUM_HONEST       = 3000     # honest session samples
NUM_CHEATING     = 3000     # cheating session samples
EPOCHS           = 40
BATCH_SIZE       = 64
LEARNING_RATE    = 0.001
WEIGHTS_DIR      = os.path.join(os.path.dirname(__file__), "weights")
WEIGHTS_PATH     = os.path.join(WEIGHTS_DIR, "temporal_lstm.pth")


# ── Helper: single event feature vector ─────────────────────────────────
def make_feature(event_type, flagged, severity):
    return [
        EVENT_TYPE_MAP.get(event_type, 0) / len(EVENT_TYPE_MAP),
        1.0 if flagged else 0.0,
        severity,
    ]


# ── Generate one honest session sequence ────────────────────────────────
def generate_honest_sequence():
    """
    Simulates a normal candidate:
    - Looks at screen consistently
    - Types at normal speed
    - One speaker
    - Normal blink rate
    - No paste events
    """
    events = []
    for _ in range(WINDOW_SIZE):
        roll = np.random.random()

        if roll < 0.30:
            # Normal gaze — looking at screen
            events.append(make_feature("gaze", False, 0.1))

        elif roll < 0.50:
            # Normal keystroke
            events.append(make_feature("keystroke", False, 0.1))

        elif roll < 0.65:
            # Normal audio — one speaker
            events.append(make_feature("audio", False, 0.1))

        elif roll < 0.75:
            # Normal head pose
            events.append(make_feature("head_pose", False, 0.1))

        elif roll < 0.83:
            # Liveness confirmed
            events.append(make_feature("liveness", False, 0.1))

        elif roll < 0.90:
            # Small paste (copy own code)
            events.append(make_feature("paste", False, 0.05))

        elif roll < 0.95:
            # Face verify — same person
            events.append(make_feature("face_verify", False, 0.1))

        else:
            # Mouse movement
            events.append(make_feature("mouse_move", False, 0.1))

    return events


# ── Generate one cheating session sequence ───────────────────────────────
def generate_cheating_sequence():
    """
    Simulates a cheating candidate using one of 4 patterns:
    1. Floating AI window (gaze lock + paste cycle)
    2. Second person helping (multiple speakers)
    3. Banned process running (ChatGPT)
    4. Mixed cheating signals
    """
    pattern = np.random.randint(0, 4)
    events  = []

    for i in range(WINDOW_SIZE):
        roll = np.random.random()

        # ── Pattern 1: Floating AI window ────────────────────────────
        if pattern == 0:
            if i % 8 < 4:
                # Gaze locked to corner — reading AI response
                events.append(make_feature(
                    "gaze", True,
                    np.random.uniform(0.7, 1.0),
                ))
            else:
                # Large paste — pasting AI answer
                events.append(make_feature(
                    "paste", True,
                    np.random.uniform(0.6, 1.0),
                ))

        # ── Pattern 2: Second person helping ─────────────────────────
        elif pattern == 1:
            if roll < 0.40:
                # Multiple speakers
                events.append(make_feature(
                    "audio", True,
                    np.random.uniform(0.7, 1.0),
                ))
            elif roll < 0.60:
                # Whisper detected
                events.append(make_feature(
                    "audio", True,
                    np.random.uniform(0.4, 0.7),
                ))
            elif roll < 0.80:
                # Occasional paste
                events.append(make_feature(
                    "paste", True,
                    np.random.uniform(0.5, 0.9),
                ))
            else:
                # Normal gaze to hide suspicion
                events.append(make_feature("gaze", False, 0.1))

        # ── Pattern 3: Banned process ─────────────────────────────────
        elif pattern == 2:
            if roll < 0.15:
                # Banned process detected
                events.append(make_feature("process", True, 1.0))
            elif roll < 0.45:
                # Gaze off screen — reading AI
                events.append(make_feature(
                    "gaze", True,
                    np.random.uniform(0.6, 0.9),
                ))
            elif roll < 0.70:
                # Large paste
                events.append(make_feature(
                    "paste", True,
                    np.random.uniform(0.7, 1.0),
                ))
            else:
                # Normal keystroke to hide suspicion
                events.append(make_feature("keystroke", False, 0.1))

        # ── Pattern 4: Mixed signals ──────────────────────────────────
        else:
            if roll < 0.20:
                events.append(make_feature(
                    "gaze", True,
                    np.random.uniform(0.5, 0.9),
                ))
            elif roll < 0.35:
                events.append(make_feature(
                    "paste", True,
                    np.random.uniform(0.4, 0.8),
                ))
            elif roll < 0.50:
                events.append(make_feature(
                    "audio", True,
                    np.random.uniform(0.5, 0.9),
                ))
            elif roll < 0.60:
                events.append(make_feature(
                    "multiple_faces", True, 0.9,
                ))
            elif roll < 0.70:
                events.append(make_feature(
                    "head_pose", True,
                    np.random.uniform(0.4, 0.8),
                ))
            else:
                # Mix in some normal events
                events.append(make_feature("keystroke", False, 0.1))

    return events


# ── Generate full dataset ────────────────────────────────────────────────
def generate_dataset():
    print(f"\n── Generating synthetic training data ──────")
    print(f"  Honest sessions  : {NUM_HONEST}")
    print(f"  Cheating sessions: {NUM_CHEATING}")
    print(f"  Window size      : {WINDOW_SIZE} events each\n")

    X, y = [], []

    for i in range(NUM_HONEST):
        X.append(generate_honest_sequence())
        y.append(0.0)   # label 0 = honest

    for i in range(NUM_CHEATING):
        X.append(generate_cheating_sequence())
        y.append(1.0)   # label 1 = cheating

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.float32)

    # Shuffle
    idx = np.random.permutation(len(X))
    X, y = X[idx], y[idx]

    print(f"  Total samples : {len(X)}")
    print(f"  X shape       : {X.shape}")
    print(f"  y shape       : {y.shape}\n")

    return X, y


# ── Train the LSTM ───────────────────────────────────────────────────────
def train():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"── Training on {device} ────────────────────────\n")

    # ── Generate data ─────────────────────────────────────────────────
    X, y = generate_dataset()

    # ── Train / val split (80/20) ─────────────────────────────────────
    split     = int(0.8 * len(X))
    X_train   = torch.FloatTensor(X[:split])
    y_train   = torch.FloatTensor(y[:split]).unsqueeze(1)
    X_val     = torch.FloatTensor(X[split:])
    y_val     = torch.FloatTensor(y[split:]).unsqueeze(1)

    train_ds  = TensorDataset(X_train, y_train)
    val_ds    = TensorDataset(X_val,   y_val)
    train_dl  = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_dl    = DataLoader(val_ds,   batch_size=BATCH_SIZE)

    # ── Model, loss, optimizer ────────────────────────────────────────
    model     = SuspiciousPatternLSTM().to(device)
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)

    best_val_loss = float("inf")
    best_val_acc  = 0.0

    print(f"{'Epoch':<8} {'Train Loss':<14} {'Val Loss':<14} {'Val Acc':<10}")
    print("-" * 50)

    # ── Training loop ─────────────────────────────────────────────────
    for epoch in range(1, EPOCHS + 1):
        # Train
        model.train()
        train_loss = 0.0
        for xb, yb in train_dl:
            xb, yb    = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            preds     = model(xb)
            loss      = criterion(preds, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item()

        train_loss /= len(train_dl)

        # Validate
        model.eval()
        val_loss  = 0.0
        correct   = 0
        total     = 0
        with torch.no_grad():
            for xb, yb in val_dl:
                xb, yb  = xb.to(device), yb.to(device)
                preds   = model(xb)
                loss    = criterion(preds, yb)
                val_loss += loss.item()
                predicted = (preds > 0.5).float()
                correct  += (predicted == yb).sum().item()
                total    += yb.size(0)

        val_loss /= len(val_dl)
        val_acc   = correct / total

        scheduler.step()

        print(f"{epoch:<8} {train_loss:<14.4f} {val_loss:<14.4f} {val_acc:<10.2%}")

        # Save best model
        if val_acc > best_val_acc:
            best_val_acc  = val_acc
            best_val_loss = val_loss
            os.makedirs(WEIGHTS_DIR, exist_ok=True)
            torch.save(model.state_dict(), WEIGHTS_PATH)

    print(f"\n── Training complete ───────────────────────")
    print(f"  Best val accuracy : {best_val_acc:.2%}")
    print(f"  Best val loss     : {best_val_loss:.4f}")
    print(f"  Weights saved to  : {WEIGHTS_PATH}\n")


# ── Entry point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    train()