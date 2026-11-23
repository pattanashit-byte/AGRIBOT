from flask import Blueprint, request, jsonify
import numpy as np

from utils.model_loader import load_crop_model
from utils.metrics_store import increment_metric
from utils.response_utils import format_response


# ============================================================
# CREATE BLUEPRINT
# ============================================================

crop_bp = Blueprint("crop", __name__)


# ============================================================
# LOAD CROP MODEL ONCE
# ============================================================

try:
    model, encoder = load_crop_model()
    print("✅ Crop model loaded successfully")

except Exception as e:
    print("❌ Error loading crop model:", str(e))
    model = None
    encoder = None


# ============================================================
# CROP PREDICTION
# ============================================================

@crop_bp.route("/predict_crop", methods=["POST"])
def predict_crop():

    try:

        # ====================================================
        # 1. CHECK MODEL
        # ====================================================

        if model is None or encoder is None:

            return jsonify(
                format_response(
                    "error",
                    "Model not loaded. Please train the model first.",
                    None
                )
            ), 500


        # ====================================================
        # 2. CHECK predict_proba SUPPORT
        # ====================================================

        if not hasattr(model, "predict_proba"):

            return jsonify(
                format_response(
                    "error",
                    "The loaded crop model does not support probability predictions.",
                    None
                )
            ), 500


        # ====================================================
        # 3. GET JSON DATA
        # ====================================================

        data = request.get_json()

        if not data:

            return jsonify(
                format_response(
                    "error",
                    "No input data received.",
                    None
                )
            ), 400


        # ====================================================
        # 4. REQUIRED FIELDS
        # ====================================================

        required_fields = [
            "N",
            "P",
            "K",
            "temperature",
            "humidity",
            "ph",
            "rainfall"
        ]


        for field in required_fields:

            if field not in data:

                return jsonify(
                    format_response(
                        "error",
                        f"Missing field: {field}",
                        None
                    )
                ), 400


        # ====================================================
        # 5. CONVERT INPUTS TO FLOAT
        # ====================================================

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

        except (ValueError, TypeError):

            return jsonify(
                format_response(
                    "error",
                    "Invalid input type. All values must be numbers.",
                    None
                )
            ), 400


        # ====================================================
        # 6. CHECK FOR NaN / INFINITY
        # ====================================================

        if not np.all(np.isfinite(input_data)):

            return jsonify(
                format_response(
                    "error",
                    "Input values must be valid finite numbers.",
                    None
                )
            ), 400


        # ====================================================
        # 7. CREATE NUMPY INPUT
        # ====================================================

        input_array = np.array(
            input_data,
            dtype=float
        ).reshape(1, -1)


        print("📥 Input Data:", input_data)


        # ====================================================
        # 8. GET PREDICTION PROBABILITIES
        # ====================================================

        probabilities = model.predict_proba(
            input_array
        )[0]


        # ====================================================
        # 9. GET TOP 3 INDICES
        # ====================================================

        top_indices = np.argsort(
            probabilities
        )[::-1][:3]


        # ====================================================
        # 10. GET MODEL CLASSES
        # ====================================================

        model_classes = getattr(
            model,
            "classes_",
            None
        )


        if model_classes is None:

            return jsonify(
                format_response(
                    "error",
                    "Unable to determine crop classes from the trained model.",
                    None
                )
            ), 500


        # ====================================================
        # 11. CREATE TOP 3 CROPS
        # ====================================================

        top_crops = []


        for index in top_indices:

            try:

                # ------------------------------------------------
                # Get actual class used by the model
                # ------------------------------------------------

                class_value = model_classes[index]


                # ------------------------------------------------
                # Decode crop name
                #
                # If LabelEncoder was used during training,
                # model class values are encoded integers.
                # ------------------------------------------------

                try:

                    crop_name = encoder.inverse_transform(
                        np.array([class_value])
                    )[0]

                except Exception:

                    # Fallback if the model already stores
                    # the original crop labels
                    crop_name = class_value


                # ------------------------------------------------
                # Probability
                # ------------------------------------------------

                probability = float(
                    probabilities[index]
                )


                # ------------------------------------------------
                # Add recommendation
                # ------------------------------------------------

                top_crops.append({

                    "rank": len(top_crops) + 1,

                    "crop": str(crop_name),

                    "probability": round(
                        probability * 100,
                        2
                    )
                })


            except Exception as crop_error:

                print(
                    "⚠️ Error decoding crop:",
                    crop_error
                )


        # ====================================================
        # 12. CHECK RESULT
        # ====================================================

        if not top_crops:

            return jsonify(
                format_response(
                    "error",
                    "Unable to generate crop recommendations.",
                    None
                )
            ), 500


        # ====================================================
        # 13. DEBUG OUTPUT
        # ====================================================

        print("\n🌾 TOP 3 CROP RECOMMENDATIONS")
        print("--------------------------------")

        for crop in top_crops:

            print(
                f"{crop['rank']}. "
                f"{crop['crop']} → "
                f"{crop['probability']}%"
            )

        print("--------------------------------\n")


        # ====================================================
        # 14. UPDATE METRICS
        # ====================================================

        increment_metric(
            "predictions"
        )


        # ====================================================
        # 15. RETURN RESPONSE
        # ====================================================

        return jsonify(
            format_response(
                "success",
                "Top 3 crop recommendations generated successfully.",
                top_crops
            )
        ), 200


    # ========================================================
    # ERROR HANDLING
    # ========================================================

    except Exception as e:

        print(
            "❌ Prediction Error:",
            str(e)
        )

        return jsonify(
            format_response(
                "error",
                "Something went wrong during crop prediction.",
                None
            )
        ), 500