from flask import Blueprint, request, jsonify
import numpy as np
from utils.model_loader import load_crop_model
from utils.metrics_store import increment_metric
from utils.response_utils import format_response

# Create Blueprint
crop_bp = Blueprint("crop", __name__)

# Load model once (important for performance)
try:
    model, encoder = load_crop_model()
    print("✅ Crop model loaded successfully")
except Exception as e:
    print("❌ Error loading crop model:", str(e))
    model = None
    encoder = None


@crop_bp.route("/predict_crop", methods=["POST"])
def predict_crop():
    try:
        # 🔹 Check if model is loaded
        if model is None or encoder is None:
            return jsonify(format_response(
                "error",
                "Model not loaded. Please train the model first.",
                None
            ))

        # 🔹 Get JSON data
        data = request.get_json()

        if not data:
            return jsonify(format_response(
                "error",
                "No input data received",
                None
            ))

        # 🔹 Required fields
        required_fields = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]

        for field in required_fields:
            if field not in data:
                return jsonify(format_response(
                    "error",
                    f"Missing field: {field}",
                    None
                ))

        # 🔹 Convert inputs to float
        try:
            input_data = [
                float(data["N"]),
                float(data["P"]),
                float(data["K"]),
                float(data["temperature"]),
                float(data["humidity"]),
                float(data["ph"]),
                float(data["rainfall"])
            ]
        except ValueError:
            return jsonify(format_response(
                "error",
                "Invalid input type. All values must be numbers.",
                None
            ))

        # 🔹 Convert to numpy array
        input_array = np.array(input_data).reshape(1, -1)

        # 🔹 Debug print (helps during testing)
        print("📥 Input Data:", input_data)

        # 🔹 Predict
        prediction = model.predict(input_array)

        # 🔹 Decode label
        crop = encoder.inverse_transform(prediction)[0]

        print("🌾 Predicted Crop:", crop)
        increment_metric("predictions")

        # 🔹 Return success response
        return jsonify(format_response(
            "success",
            "Crop predicted successfully",
            crop
        ))

    except Exception as e:
        print("❌ Prediction Error:", str(e))
        return jsonify(format_response(
            "error",
            "Something went wrong during prediction",
            None
        ))
