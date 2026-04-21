import joblib
import os
import numpy as np

BASE_DIR = "/Users/ashit/Desktop/MINI_PROJECT/AGRIBOT"

def predict_crop(input_data):
    model_path = os.path.join(BASE_DIR, "models/saved_model/crop_model.pkl")
    encoder_path = os.path.join(BASE_DIR, "models/saved_model/label_encoder.pkl")

    model = joblib.load(model_path)
    le = joblib.load(encoder_path)

    input_array = np.array(input_data).reshape(1, -1)

    prediction = model.predict(input_array)
    crop = le.inverse_transform(prediction)

    return crop[0]


if __name__ == "__main__":
    sample = [90, 42, 43, 20.5, 80, 6.5, 200]
    print("Predicted Crop:", predict_crop(sample))