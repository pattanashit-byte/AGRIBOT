import joblib
import tensorflow as tf
import os

BASE_DIR = "/Users/ashit/Desktop/MINI_PROJECT/AGRIBOT"

def load_crop_model():
    model_path = os.path.join(BASE_DIR, "models/saved_model/crop_model.pkl")
    encoder_path = os.path.join(BASE_DIR, "models/saved_model/label_encoder.pkl")

    model = joblib.load(model_path)
    encoder = joblib.load(encoder_path)

    return model, encoder


def load_disease_model():
    model_path = os.path.join(BASE_DIR, "models/saved_model/disease_model.h5")
    model = tf.keras.models.load_model(model_path)

    return model