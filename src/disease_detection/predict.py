import tensorflow as tf
import numpy as np
import os
import sys

BASE_DIR = "/Users/ashit/Desktop/MINI_PROJECT/AGRIBOT"
sys.path.append(BASE_DIR)

from utils.disease_labels import get_best_disease_for_plant, get_disease_name
from utils.image_utils import preprocess_image

def predict_disease(image_path, plant_name=None):
    model_path = os.path.join(BASE_DIR, "models/saved_model/disease_model.h5")

    model = tf.keras.models.load_model(model_path)

    img = preprocess_image(image_path)

    prediction = model.predict(img, verbose=0)[0]

    if plant_name:
        plant_specific_prediction = get_best_disease_for_plant(prediction, plant_name)
        if plant_specific_prediction:
            return plant_specific_prediction

    predicted_class = int(np.argmax(prediction))

    return get_disease_name(predicted_class)


if __name__ == "__main__":
    test_img = os.path.join(BASE_DIR, "static/uploads/test.jpg")
    print("Detected Disease:", predict_disease(test_img))
