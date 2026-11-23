import joblib
import tensorflow as tf
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Cached model references (loaded once on first call) ────────────────────────
_crop_model = None
_crop_encoder = None
_disease_model = None


def load_crop_model():
    global _crop_model, _crop_encoder
    if _crop_model is None:
        model_path = os.path.join(BASE_DIR, "models/saved_model/crop_model.pkl")
        encoder_path = os.path.join(BASE_DIR, "models/saved_model/label_encoder.pkl")
        _crop_model = joblib.load(model_path)
        _crop_encoder = joblib.load(encoder_path)
    return _crop_model, _crop_encoder


def load_disease_model():
    global _disease_model
    if _disease_model is None:
        model_path = os.path.join(BASE_DIR, "models/saved_model/disease_model.h5")
        _disease_model = tf.keras.models.load_model(model_path)
    return _disease_model