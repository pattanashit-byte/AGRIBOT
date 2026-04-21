from flask import Blueprint, request, jsonify
import os
from utils.disease_labels import get_plant_display_name, get_plant_prediction_summary, is_supported_plant
from utils.model_loader import load_disease_model
from utils.metrics_store import increment_metric
from utils.image_utils import preprocess_image
from utils.response_utils import format_response

disease_bp = Blueprint("disease", __name__)

model = load_disease_model()

UPLOAD_FOLDER = "static/uploads"
HEALTHY_CONFIDENCE_FLOOR = 0.78
DISEASE_CONFIDENCE_FLOOR = 0.18
HEALTHY_MARGIN_FLOOR = 0.12

@disease_bp.route("/predict_disease", methods=["POST"])
def predict_disease():
    try:
        file = request.files["file"]
        selected_plant = request.form.get("plant_name", "").strip()

        if not file:
            return jsonify(format_response("error", "No file uploaded", None))

        if not selected_plant:
            return jsonify(format_response("error", "Please select the plant before scanning.", None))

        if not is_supported_plant(selected_plant):
            return jsonify(format_response(
                "error",
                f"{selected_plant} is not supported by the current disease model.",
                None,
            ))

        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        img = preprocess_image(filepath)

        prediction = model.predict(img, verbose=0)[0]
        prediction_summary = get_plant_prediction_summary(prediction, selected_plant)

        if not prediction_summary:
            return jsonify(format_response("error", "No disease classes found for the selected plant.", None))

        if not prediction_summary["has_disease_classes"]:
            return jsonify(format_response(
                "error",
                f"{prediction_summary['plant_label']} only has healthy samples in the current model, so disease diagnosis is not available yet.",
                None,
            ))

        diagnosis_name = prediction_summary["best_name"]
        response_message = "Disease detected."

        if prediction_summary["best_is_healthy"]:
            healthy_margin = prediction_summary["best_score"] - prediction_summary["top_disease_score"]

            if (
                prediction_summary["top_disease_name"]
                and prediction_summary["best_score"] < HEALTHY_CONFIDENCE_FLOOR
                and prediction_summary["top_disease_score"] >= DISEASE_CONFIDENCE_FLOOR
                and healthy_margin <= HEALTHY_MARGIN_FLOOR
            ):
                diagnosis_name = f"Possible {prediction_summary['top_disease_name']}"
                response_message = (
                    f"The healthy prediction for {prediction_summary['plant_label']} was uncertain, "
                    "so the closest disease match is shown."
                )
            else:
                response_message = f"{get_plant_display_name(selected_plant)} appears healthy based on the current model."

        increment_metric("disease_scans")

        return jsonify(format_response("success", response_message, diagnosis_name))

    except Exception as e:
        return jsonify(format_response("error", str(e), None))
