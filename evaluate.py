"""
Evaluation of the Agribot disease CNN -> numbers for Table 6.1.

Run from the project root (next to app.py), inside your venv:

    python evaluate_disease_model.py
    python evaluate_disease_model.py models/saved_model/other_model.h5 resnet50

Arguments (both optional):
    1) path to a .h5 / .keras model       (default: models/saved_model/disease_model.h5)
    2) preprocessing: rgb255 | resnet50   (default: rgb255)
         rgb255   -> RGB, divided by 255      (what the app uses now)
         resnet50 -> keras.applications.resnet50.preprocess_input

It reports: number of classes, test accuracy, macro precision / recall / F1,
and average inference time per image. It does not change any app file.

IMPORTANT: the test images must NOT have been used for training. If you have
a dedicated test folder, set TEST_DIR below. Otherwise a stratified 80/20 split
with a fixed seed is made - this is only a valid test set if your training
used a split that excludes it. Use the same split as your training notebook.
"""
import json
import os
import random
import sys
import time

import cv2
import numpy as np
import tensorflow as tf
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split

ROOT = os.path.dirname(os.path.abspath(__file__))

# ----------------------------- CONFIG ---------------------------------------
MODEL_PATH = os.path.join(ROOT, "models", "saved_model", "disease_model.h5")
DATASET_DIR = os.path.join(ROOT, "dataset", "disease", "plantvillage dataset", "color")

# Folder with the same class sub-folders, holding ONLY held-out test images.
# Leave None to make a stratified split from DATASET_DIR instead.
TEST_DIR = None

TEST_SIZE = 0.2        # used only when TEST_DIR is None
SEED = 42              # use the SAME seed/split as your training
BATCH_SIZE = 64
LATENCY_IMAGES = 200   # images used for the timing test
PREPROCESS = "rgb255"
# ----------------------------------------------------------------------------

if len(sys.argv) > 1:
    MODEL_PATH = sys.argv[1]
if len(sys.argv) > 2:
    PREPROCESS = sys.argv[2].lower()

EXTS = (".jpg", ".jpeg", ".png")
OUT_DIR = os.path.join(ROOT, "evaluation_results")
os.makedirs(OUT_DIR, exist_ok=True)

print(f"\nModel      : {MODEL_PATH}")
model = tf.keras.models.load_model(MODEL_PATH)
height, width = int(model.input_shape[1] or 128), int(model.input_shape[2] or 128)
n_outputs = int(model.output_shape[-1])
print(f"Input size : {height}x{width} | outputs: {n_outputs} | preprocessing: {PREPROCESS}")
print(f"First layers: {[l.__class__.__name__ for l in model.layers[:5]]}")

# ----------------------------- DATA -----------------------------------------
base_dir = TEST_DIR or DATASET_DIR
class_names = sorted(
    d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))
)

if len(class_names) != n_outputs:
    sys.exit(
        f"\n❌ Folder has {len(class_names)} classes but the model has {n_outputs} "
        "outputs. Class order/number does not match this model."
    )

paths, labels = [], []
for idx, name in enumerate(class_names):
    folder = os.path.join(base_dir, name)
    for fname in sorted(os.listdir(folder)):
        if fname.lower().endswith(EXTS):
            paths.append(os.path.join(folder, fname))
            labels.append(idx)

if TEST_DIR:
    test_paths, test_labels = paths, labels
    print(f"Using dedicated test folder: {len(test_paths)} images")
else:
    _, test_paths, _, test_labels = train_test_split(
        paths, labels, test_size=TEST_SIZE, stratify=labels, random_state=SEED
    )
    print(
        f"Stratified split (seed={SEED}): {len(test_paths)} test images of {len(paths)}\n"
        "⚠️  Valid only if your training did NOT use these images."
    )


def load_one(path):
    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Unable to read image: {path}")
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (width, height)).astype(np.float32)
    if PREPROCESS == "resnet50":
        img = tf.keras.applications.resnet50.preprocess_input(img)
    else:
        img = img / 255.0
    return img


# ----------------------------- ACCURACY / PRECISION / RECALL / F1 -----------
print("\nPredicting on the test set...")
chunks = []
for start in range(0, len(test_paths), BATCH_SIZE):
    batch = np.stack([load_one(p) for p in test_paths[start:start + BATCH_SIZE]])
    chunks.append(model.predict(batch, verbose=0))
    if (start // BATCH_SIZE) % 20 == 0:
        print(f"   {min(start + BATCH_SIZE, len(test_paths))}/{len(test_paths)}")

y_true = np.asarray(test_labels)
y_pred = np.concatenate(chunks).argmax(axis=1)
all_labels = list(range(n_outputs))

accuracy = accuracy_score(y_true, y_pred)
precision, recall, f1, _ = precision_recall_fscore_support(
    y_true, y_pred, labels=all_labels, average="macro", zero_division=0
)

report = classification_report(
    y_true, y_pred, labels=all_labels, target_names=class_names,
    digits=4, zero_division=0,
)

# ----------------------------- INFERENCE TIME -------------------------------
print("\nMeasuring inference time (one image at a time, like the app)...")
sample = random.Random(SEED).sample(test_paths, min(LATENCY_IMAGES, len(test_paths)))

warm = np.expand_dims(load_one(sample[0]), axis=0)
for _ in range(5):                       # warm-up, not counted
    model.predict(warm, verbose=0)

model_ms, total_ms = [], []
for path in sample:
    t0 = time.perf_counter()
    x = np.expand_dims(load_one(path), axis=0)
    t1 = time.perf_counter()
    model.predict(x, verbose=0)
    t2 = time.perf_counter()
    model_ms.append((t2 - t1) * 1000)
    total_ms.append((t2 - t0) * 1000)

avg_model_ms = float(np.mean(model_ms))
avg_total_ms = float(np.mean(total_ms))

# ----------------------------- SAVE -----------------------------------------
results = {
    "model": os.path.basename(MODEL_PATH),
    "preprocessing": PREPROCESS,
    "number_of_classes": n_outputs,
    "test_images": int(len(test_paths)),
    "test_accuracy_percent": round(accuracy * 100, 2),
    "macro_precision_percent": round(precision * 100, 2),
    "macro_recall_percent": round(recall * 100, 2),
    "macro_f1_percent": round(f1 * 100, 2),
    "avg_inference_ms_model_only": round(avg_model_ms, 1),
    "avg_inference_ms_with_preprocessing": round(avg_total_ms, 1),
}

with open(os.path.join(OUT_DIR, "results.json"), "w") as fh:
    json.dump(results, fh, indent=2)

with open(os.path.join(OUT_DIR, "classification_report.txt"), "w") as fh:
    fh.write(report)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cm = confusion_matrix(y_true, y_pred, labels=all_labels)
    row_sums = cm.sum(axis=1, keepdims=True)
    cm_norm = np.divide(
        cm, row_sums, out=np.zeros(cm.shape, dtype=float), where=row_sums != 0
    )

    fig, ax = plt.subplots(figsize=(14, 12))
    im = ax.imshow(cm_norm, cmap="Blues", vmin=0, vmax=1)
    ax.set_title("Confusion matrix of the improved CNN on the test set (row-normalised)")
    ax.set_xlabel("Predicted class")
    ax.set_ylabel("True class")
    ticks = np.arange(n_outputs)
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels(ticks, fontsize=7)
    ax.set_yticklabels(ticks, fontsize=7)
    fig.colorbar(im, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "confusion_matrix.png"), dpi=300)
    plt.close(fig)

    # Key that maps the numbers on the axes to class names (put it in an appendix)
    with open(os.path.join(OUT_DIR, "class_index_key.txt"), "w") as fh:
        for i, name in enumerate(class_names):
            fh.write(f"{i:2d}  {name}\n")
except Exception as exc:  # matplotlib missing is not fatal
    print(f"(confusion matrix image skipped: {exc})")

# ----------------------------- PRINT ----------------------------------------
print("\n" + report)
print("=" * 60)
print("VALUES FOR TABLE 6.1")
print("=" * 60)
print(f"Model                        : {os.path.basename(MODEL_PATH)}")
print(f"Number of disease classes    : {n_outputs}")
print(f"Test accuracy                : {accuracy * 100:.2f} %")
print(f"Precision (macro)            : {precision * 100:.2f} %")
print(f"Recall (macro)               : {recall * 100:.2f} %")
print(f"F1-score (macro)             : {f1 * 100:.2f} %")
print(f"Avg inference time per image : {avg_model_ms:.1f} ms (model only)")
print(f"                               {avg_total_ms:.1f} ms (incl. image loading)")
print("=" * 60)
print(f"Files saved in: {OUT_DIR}")