from flask import Blueprint, request, jsonify
import collections
import os
import random
import traceback
import uuid

import cv2
import numpy as np

from utils.disease_labels import (
    DISEASE_DATASET_DIR,
    DISEASE_LABELS,
    PLANT_TO_LABEL_INDEXES,
    get_plant_display_name,
    get_plant_prediction_summary,
    is_supported_plant,
    resolve_plant_key,
)

from utils.model_loader import load_disease_model
from utils.metrics_store import increment_metric
from utils.response_utils import format_response
from utils.image_checks import (
    ImageCheckError,
    load_and_normalize,
    plant_pixel_ratio,
    save_as_jpeg,
    sharpness_score,
)
from utils.online_fallback import diagnose_online, is_enabled as online_enabled


# ============================================================
# DISEASE BLUEPRINT
# ============================================================

disease_bp = Blueprint("disease", __name__)


# ============================================================
# CONFIGURATION
# ============================================================

# Absolute path, so it works no matter which folder you start Flask from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Uploaded photos are deleted after the scan (set KEEP_DISEASE_UPLOADS=1 to keep).
KEEP_UPLOADS = os.getenv("KEEP_DISEASE_UPLOADS", "0") == "1"

# Prints top-5 predictions to the terminal for every scan.  Off:  DISEASE_DEBUG=0
DEBUG = os.getenv("DISEASE_DEBUG", "1") == "1"

# Self-test at startup using your dataset images.      Off:  DISEASE_CALIBRATE=0
CALIBRATE = os.getenv("DISEASE_CALIBRATE", "1") == "1"
CALIBRATION_SAMPLES_PER_CLASS = int(os.getenv("CALIBRATION_SAMPLES", "6"))


# ---- How sure must the local CNN be before we show its answer? ----------
# These scores are measured WITHIN the plant the user selected
# (that plant's class scores are renormalised to sum to 1).
DISEASE_CONFIDENT = 0.80          # best disease class must reach this
HEALTHY_CONFIDENT = 0.80          # best "healthy" class must reach this
HEALTHY_MAX_DISEASE_SCORE = 0.15  # ...and no disease may be this likely

# Raw probability mass the model gave to the selected plant.
OTHER_PLANT_GLOBAL_TOP = 0.90     # another plant at >= this ...
OTHER_PLANT_SELECTED_MAX = 0.05   # ... and selected plant below this -> other plant
MIN_PLANT_MASS = 0.20             # below this -> uncertain

# Photo sanity checks
MIN_PLANT_PIXEL_RATIO = 0.05      # below this: not a leaf photo
BLURRY_SHARPNESS = 25.0           # below this: suggest a sharper photo

# Online second opinion must be at least this confident to be shown
ONLINE_MIN_PROBABILITY = 0.50


SCAN_TIPS = [
    "Photograph a single leaf and fill most of the frame with it.",
    "Use natural daylight and avoid strong shadows, flash glare and filters.",
    "Keep the leaf in focus, ideally against a plain background.",
    "Make sure the plant selected above matches the plant in the photo.",
    "If the problem is on fruit, stems or roots, add a photo of an affected leaf too.",
]


# ============================================================
# LOAD CNN MODEL ONCE
# ============================================================

model = None
MODEL_PROBLEM = None   # set when the model and label list don't match

try:
    model = load_disease_model()
    print("✅ Disease CNN model loaded successfully")
except Exception as e:
    model = None
    print(f"❌ Failed to load disease CNN model: {e}")


# ============================================================
# PREPROCESSING + LABEL ALIGNMENT (filled in by calibration)
# ============================================================

# rgb255 = RGB, divided by 255   (what the old preprocess_image did)
PREPROCESS_MODE = "rgb255"
PREPROCESS_MODES = ["rgb255", "rgb_raw", "bgr255", "bgr_raw"]

# None = model output index i is DISEASE_LABELS[i].
# Otherwise a list: model output index -> index in DISEASE_LABELS.
OUTPUT_TO_LABEL = None

_IMG_EXTS = (".jpg", ".jpeg", ".png")


def _model_input_size():
    try:
        return int(model.input_shape[1] or 128), int(model.input_shape[2] or 128)
    except Exception:
        return 128, 128


def _load_array(path, mode):
    """Read an image file and prepare it the way `mode` says."""
    img = cv2.imread(path)
    if img is None:
        return None

    if mode.startswith("rgb"):
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    height, width = _model_input_size()
    img = cv2.resize(img, (width, height)).astype(np.float32)

    if mode.endswith("255"):
        img = img / 255.0

    return img


def _align(prediction):
    """Reorder model outputs so index i always means DISEASE_LABELS[i]."""
    scores = np.asarray(prediction, dtype=np.float64).ravel()

    if OUTPUT_TO_LABEL is None:
        return scores

    aligned = np.zeros(len(DISEASE_LABELS), dtype=np.float64)
    for output_index, label_index in enumerate(OUTPUT_TO_LABEL):
        if 0 <= label_index < len(DISEASE_LABELS) and output_index < scores.size:
            aligned[label_index] = scores[output_index]
    return aligned


# ============================================================
# STARTUP CHECKS + AUTO-CALIBRATION
# ============================================================

def _run_startup_checks():
    global MODEL_PROBLEM

    if model is None:
        return

    try:
        n_outputs = int(model.output_shape[-1])
    except Exception:
        n_outputs = None

    n_labels = len(DISEASE_LABELS)

    print(f"🔎 Model outputs: {n_outputs} | Labels from dataset folder: {n_labels}")
    print(f"🔎 Model input shape: {model.input_shape}")
    print(f"🔎 First layers: {[l.__class__.__name__ for l in model.layers[:5]]}")

    if n_labels == 0:
        MODEL_PROBLEM = (
            "No disease labels were found. Check that the folder "
            "'dataset/disease/plantvillage dataset/color' exists."
        )
        print(f"❌ {MODEL_PROBLEM}")
        return

    if n_outputs is not None and n_outputs != n_labels:
        MODEL_PROBLEM = (
            f"The model has {n_outputs} outputs but the dataset folder has "
            f"{n_labels} classes, so labels cannot be matched to the model."
        )
        print(f"❌ {MODEL_PROBLEM}")


def _calibrate():
    """
    Feed real dataset images through the model and work out
      (1) which preprocessing it expects, and
      (2) whether its output order differs from the label list.
    The result is applied automatically to every scan.
    """
    global PREPROCESS_MODE, OUTPUT_TO_LABEL

    if model is None or MODEL_PROBLEM or not CALIBRATE:
        return

    rng = random.Random(0)
    samples = []

    for label_index, label in enumerate(DISEASE_LABELS):
        folder = os.path.join(DISEASE_DATASET_DIR, label)
        try:
            files = [f for f in os.listdir(folder) if f.lower().endswith(_IMG_EXTS)]
        except OSError:
            continue
        rng.shuffle(files)
        for name in files[:CALIBRATION_SAMPLES_PER_CLASS]:
            samples.append((os.path.join(folder, name), label_index))

    if len(samples) < 20:
        print("⚠️  Calibration skipped: not enough dataset images found.")
        return

    print(f"🔧 Calibrating on {len(samples)} dataset images...")

    best = None

    for order, mode in enumerate(PREPROCESS_MODES):
        arrays, truths = [], []
        for path, truth in samples:
            arr = _load_array(path, mode)
            if arr is not None:
                arrays.append(arr)
                truths.append(truth)

        if not arrays:
            continue

        truths = np.asarray(truths)
        predicted = model.predict(np.stack(arrays), batch_size=32, verbose=0).argmax(axis=1)

        accuracy = float((predicted == truths).mean())

        by_output = collections.defaultdict(list)
        for out_idx, true_idx in zip(predicted, truths):
            by_output[int(out_idx)].append(int(true_idx))

        # "purity": do predictions map cleanly onto single true classes?
        purity = sum(
            max(collections.Counter(v).values()) for v in by_output.values()
        ) / len(predicted)

        print(f"   {mode:8s} accuracy={accuracy * 100:5.1f}%  mapping-purity={purity * 100:5.1f}%")

        candidate = (purity, accuracy, -order)
        if best is None or candidate > best[0]:
            best = (candidate, mode, accuracy, purity, by_output)

    if best is None:
        print("⚠️  Calibration failed: no images could be read.")
        return

    _, mode, accuracy, purity, by_output = best
    PREPROCESS_MODE = mode
    print(f"🔧 Preprocessing chosen: {mode}")

    # Accuracy ~ purity means every output already maps to its own label.
    if accuracy >= 0.80 or accuracy >= purity - 0.03:
        OUTPUT_TO_LABEL = None
        print("✅ Label order is correct for dataset images.")
        print("   If real photos still fail, it is the lab-vs-real-photo gap, not a bug.")
        return

    if purity >= 0.80:
        mapping = {
            out_idx: collections.Counter(trues).most_common(1)[0][0]
            for out_idx, trues in by_output.items()
        }

        if len(set(mapping.values())) == len(mapping):
            n_outputs = int(model.output_shape[-1])
            leftover = [i for i in range(len(DISEASE_LABELS)) if i not in set(mapping.values())]

            full = []
            for out_idx in range(n_outputs):
                if out_idx in mapping:
                    full.append(mapping[out_idx])
                elif leftover:
                    full.append(leftover.pop(0))
                else:
                    full.append(-1)

            OUTPUT_TO_LABEL = full
            print("⚠️  Label order did NOT match the model. Auto-corrected for all scans.")
            return

    print(
        "❌ Calibration could not explain the model's behaviour. The model may "
        "have been trained on different classes or a different image size. "
        "Using the default settings."
    )


_run_startup_checks()
_calibrate()


# ============================================================
# RESPONSE HELPERS
# ============================================================

def _payload(result_type, **values):
    """Every response carries the same keys, so the frontend never breaks."""
    data = {
        "result_type": result_type,   # disease | healthy | online |
                                      # uncertain | other_plant | not_plant
        "title": None,
        "disease_name": None,
        "confidence": None,
        "plant_name": None,
        "plant_key": None,
        "is_healthy": False,
        "source": None,
        "description": None,
        "treatment_sections": [],
        "alternatives": [],
        "tips": [],
    }
    data.update(values)
    return data


def _ok(message, data):
    return jsonify(format_response("success", message, data))


def _error(message, status_code):
    return jsonify(format_response("error", message, None)), status_code


# ============================================================
# LOCAL CNN DECISION
# ============================================================

def build_plant_scores(scores, selected_plant):
    """
    The user already told us which plant this is, so judge the photo only
    against THAT plant's classes.

    Returns (relative_scores, plant_mass, global_top, global_top_is_selected)
    """
    plant_key = resolve_plant_key(selected_plant)
    indexes = PLANT_TO_LABEL_INDEXES.get(plant_key, [])

    plant_mass = float(sum(scores[i] for i in indexes))
    global_top_index = int(scores.argmax())
    global_top = float(scores[global_top_index])

    relative = np.zeros_like(scores)
    if plant_mass > 0:
        for i in indexes:
            relative[i] = scores[i] / plant_mass

    return relative, plant_mass, global_top, global_top_index in indexes


def assess_local_prediction(summary, plant_mass, global_top, global_top_is_selected):
    """
    Returns one of:
        "disease" | "healthy" | "other_plant" | "uncertain"
    """
    best = float(summary["best_score"])
    top_disease = float(summary.get("top_disease_score") or 0.0)

    if (
        not global_top_is_selected
        and global_top >= OTHER_PLANT_GLOBAL_TOP
        and plant_mass < OTHER_PLANT_SELECTED_MAX
    ):
        return "other_plant"

    if plant_mass < MIN_PLANT_MASS:
        return "uncertain"

    if summary["best_is_healthy"]:
        if best >= HEALTHY_CONFIDENT and top_disease < HEALTHY_MAX_DISEASE_SCORE:
            return "healthy"
        return "uncertain"

    if best >= DISEASE_CONFIDENT:
        return "disease"

    return "uncertain"


def _debug_print(scores, selected_plant, img, plant_mass, global_top, verdict):
    if not DEBUG:
        return

    top5 = np.argsort(scores)[::-1][:5]

    print("\n" + "=" * 70)
    print(f"SELECTED PLANT : {selected_plant}")
    print(f"PREPROCESSING  : {PREPROCESS_MODE} | shape={img.shape} "
          f"min={img.min():.3f} max={img.max():.3f}")
    print("TOP-5 (raw softmax, after label alignment):")
    for i in top5:
        label = DISEASE_LABELS[i] if i < len(DISEASE_LABELS) else f"<index {i}>"
        print(f"   {int(i):2d}  {label:55s} {scores[i]:.3f}")
    print(f"SELECTED-PLANT MASS : {plant_mass:.3f}")
    print(f"GLOBAL TOP          : {global_top:.3f}")
    print(f"VERDICT             : {verdict}")
    print("=" * 70 + "\n")


# ============================================================
# DISEASE PREDICTION
# ============================================================

@disease_bp.route("/predict_disease", methods=["POST"])
def predict_disease():

    filepath = None

    try:

        # ----------------------------------------------------
        # Check CNN model
        # ----------------------------------------------------

        if model is None:
            return _error("Disease detection model is not available.", 500)

        if MODEL_PROBLEM:
            return _error(f"Model configuration problem: {MODEL_PROBLEM}", 500)

        # ----------------------------------------------------
        # Check uploaded file + selected plant
        # ----------------------------------------------------

        if "file" not in request.files:
            return _error("No file uploaded.", 400)

        file = request.files["file"]

        if file.filename == "":
            return _error("No image selected.", 400)

        selected_plant = request.form.get("plant_name", "").strip()

        if not selected_plant:
            return _error("Please select the plant before scanning.", 400)

        if not is_supported_plant(selected_plant):
            return _error(
                f"{selected_plant} is not supported by the current disease model.",
                400,
            )

        plant_label = get_plant_display_name(selected_plant)

        # ----------------------------------------------------
        # Validate + clean the image (rotation, size, format)
        # ----------------------------------------------------

        try:
            image = load_and_normalize(file)
        except ImageCheckError as exc:
            return _error(str(exc), 400)

        filepath = os.path.join(UPLOAD_FOLDER, f"disease_{uuid.uuid4().hex}.jpg")
        save_as_jpeg(image, filepath)

        # ----------------------------------------------------
        # Is this even a plant photo?
        # ----------------------------------------------------

        tips = list(SCAN_TIPS)

        if sharpness_score(image) < BLURRY_SHARPNESS:
            tips.insert(0, "The photo looks blurry. Hold the phone steady and tap the leaf to focus.")

        if plant_pixel_ratio(image) < MIN_PLANT_PIXEL_RATIO:
            return _ok(
                "No leaf was found in this photo, so no diagnosis was made.",
                _payload(
                    "not_plant",
                    title="This doesn't look like a leaf",
                    plant_name=plant_label,
                    plant_key=selected_plant,
                    tips=tips,
                ),
            )

        # ----------------------------------------------------
        # CNN PREDICTION
        # ----------------------------------------------------

        arr = _load_array(filepath, PREPROCESS_MODE)
        if arr is None:
            raise ValueError(f"Unable to read image: {filepath}")

        img = np.expand_dims(arr, axis=0)

        raw_prediction = model.predict(img, verbose=0)[0]

        # Make output index i mean DISEASE_LABELS[i] (auto-corrected at startup)
        scores = _align(raw_prediction)

        # Judge the photo only against the plant the user selected.
        relative, plant_mass, global_top, top_is_selected = build_plant_scores(
            scores, selected_plant
        )

        summary = get_plant_prediction_summary(relative, selected_plant)

        if not summary:
            return _error("No disease classes found for the selected plant.", 400)

        if not summary["has_disease_classes"]:
            return _error(
                f"{summary['plant_label']} only has healthy samples in the "
                "current model, so disease diagnosis is not available yet.",
                400,
            )

        increment_metric("disease_scans")

        verdict = assess_local_prediction(
            summary, plant_mass, global_top, top_is_selected
        )

        _debug_print(scores, selected_plant, img, plant_mass, global_top, verdict)

        # ----------------------------------------------------
        # CONFIDENT LOCAL RESULTS
        # ----------------------------------------------------

        if verdict == "disease":
            return _ok(
                "Disease detected.",
                _payload(
                    "disease",
                    disease_name=summary["best_name"],
                    confidence=round(float(summary["best_score"]) * 100, 2),
                    plant_name=plant_label,
                    plant_key=selected_plant,
                    source="Agribot CNN model",
                ),
            )

        if verdict == "healthy":
            return _ok(
                f"{plant_label} appears healthy based on the current model.",
                _payload(
                    "healthy",
                    disease_name=f"{plant_label} Healthy",
                    confidence=round(float(summary["best_score"]) * 100, 2),
                    plant_name=plant_label,
                    plant_key=selected_plant,
                    is_healthy=True,
                    source="Agribot CNN model",
                ),
            )

        # ----------------------------------------------------
        # NOT SURE -> ask the online model for a second opinion
        # ----------------------------------------------------

        if online_enabled():

            online = diagnose_online(filepath)

            if online.get("ok") and online["probability"] >= ONLINE_MIN_PROBABILITY:

                crop = online.get("crop_name")

                if online["is_healthy"]:
                    message = "The online model finds no disease on this leaf."
                else:
                    message = (
                        "Our own model wasn't certain, so this result comes "
                        "from an online crop-health model."
                    )

                if crop:
                    message += f" It identified the crop as {crop}."

                return _ok(
                    message,
                    _payload(
                        "online",
                        disease_name=online["disease_name"],
                        confidence=round(online["probability"] * 100, 2),
                        plant_name=crop or plant_label,
                        plant_key=selected_plant,
                        is_healthy=online["is_healthy"],
                        source="Online crop-health model (Kindwise)",
                        description=online.get("description"),
                        treatment_sections=online.get("treatment_sections", []),
                        alternatives=[
                            {
                                "name": alt["name"],
                                "confidence": round(alt["probability"] * 100, 1),
                            }
                            for alt in online.get("alternatives", [])
                        ],
                    ),
                )

        # ----------------------------------------------------
        # NO TRUSTWORTHY ANSWER -> never show a guessed disease
        # ----------------------------------------------------

        if verdict == "other_plant":
            return _ok(
                f"This leaf doesn't look like {plant_label} to the model, so no "
                "diagnosis is shown. Check the plant you selected or try another photo.",
                _payload(
                    "other_plant",
                    title=f"This may not be a {plant_label} leaf",
                    plant_name=plant_label,
                    plant_key=selected_plant,
                    tips=tips,
                ),
            )

        return _ok(
            "The photo doesn't clearly match any condition the model knows, so "
            "no diagnosis is shown instead of a wrong one.",
            _payload(
                "uncertain",
                title="We couldn't identify this leaf reliably",
                plant_name=plant_label,
                plant_key=selected_plant,
                tips=tips,
            ),
        )

    # ========================================================
    # ERROR HANDLING
    # ========================================================

    except Exception:

        print("❌ Disease prediction error:")
        traceback.print_exc()

        return _error(
            "Something went wrong while analysing this image. "
            "Please try another photo.",
            500,
        )

    finally:

        if filepath and not KEEP_UPLOADS:
            try:
                os.remove(filepath)
            except OSError:
                pass