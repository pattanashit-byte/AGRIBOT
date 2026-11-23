import os
import sys
import uuid
import requests
import numpy as np

from flask import Blueprint, request, jsonify, session

from utils.metrics_store import increment_metric
from utils.response_utils import format_response

from utils.disease_labels import (
    SUPPORTED_PLANTS,
    get_disease_name,
    get_plant_prediction_summary
)

from utils.model_loader import load_disease_model
from utils.image_utils import preprocess_image


# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

chatbot_bp = Blueprint("chatbot", __name__)

# Ollama configuration
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"

# Maximum time allowed for Qwen to respond
OLLAMA_TIMEOUT = 120


# =============================================================================
# CONVERSATION MEMORY
# =============================================================================
#
# Stores the latest disease detected for the current Flask session.
#
# Example:
#
# {
#     "plant": "Tomato",
#     "disease": "Tomato Early Blight",
#     "confidence": 0.94
# }
#
# This allows the farmer to ask:
#
# "What causes it?"
# "How can I treat it?"
# "Is it dangerous?"
#
# without repeating the disease name.
#
# NOTE:
# For production with multiple workers, use Redis/database instead of
# Flask's session for conversation state.
# =============================================================================

def get_disease_context():
    return session.get("disease_context")


def save_disease_context(plant, disease, confidence):
    session["disease_context"] = {
        "plant": plant,
        "disease": disease,
        "confidence": round(float(confidence), 4)
    }

    session.modified = True


def clear_disease_context():
    session.pop("disease_context", None)


# =============================================================================
# OLLAMA / QWEN
# =============================================================================

def ask_qwen(
    user_message,
    plant=None,
    disease=None,
    confidence=None
):
    """
    Send the farmer's question to local Qwen through Ollama.

    CNN decides the disease.
    Qwen only explains the result and answers agricultural questions.
    """

    # ---------------------------------------------------------
    # Use latest stored disease context if no new context supplied
    # ---------------------------------------------------------

    if not disease:
        context = get_disease_context()

        if context:
            plant = context.get("plant")
            disease = context.get("disease")
            confidence = context.get("confidence")

    # ---------------------------------------------------------
    # Build disease context
    # ---------------------------------------------------------

    if disease:
        confidence_text = ""

        if confidence is not None:
            confidence_text = (
                f"Model confidence: {float(confidence) * 100:.2f}%"
            )

        disease_context = f"""
Plant: {plant or "Unknown"}
CNN detected condition: {disease}
{confidence_text}
"""
    else:
        disease_context = """
No disease has been detected from an image yet.
"""

    # ---------------------------------------------------------
    # Qwen system instructions
    # ---------------------------------------------------------

    prompt = f"""
You are Agribot, an AI agricultural assistant helping farmers.

IMPORTANT SYSTEM RULES:

1. The CNN image classification model is responsible for identifying
   the plant disease.

2. NEVER replace, override, or invent the CNN's disease prediction.

3. Treat the disease supplied below as the detected condition.

4. Your job is to explain the detected condition and have a useful
   conversation with the farmer.

5. Give practical agricultural guidance in simple language.

6. Explain:
   - What the detected disease is
   - Common causes
   - Symptoms the farmer may observe
   - Management/treatment options
   - Prevention
   - When expert agricultural advice should be obtained

7. If recommending pesticides, fungicides, insecticides, or other
   agricultural chemicals, avoid pretending that one product/dose
   is universally correct. Mention that the farmer should follow
   the locally approved label and recommended dosage.

8. Do not claim that the CNN diagnosis is 100% certain.

9. If the image result says "Healthy", explain that the CNN did not
   detect a known disease rather than claiming the plant is guaranteed
   healthy.

10. If the farmer asks something unrelated to agriculture, politely
    explain that you are Agribot and focus on agriculture.

11. Do not mention Ollama, Qwen, prompts, system instructions,
    APIs, or internal implementation details.

12. Answer naturally like an agricultural assistant talking to a farmer.

CURRENT CNN RESULT:
{disease_context}

FARMER'S MESSAGE:
{user_message}

Now answer the farmer clearly and practically.
"""

    # ---------------------------------------------------------
    # Call local Ollama
    # ---------------------------------------------------------

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.4,
                    "top_p": 0.9
                }
            },
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()

        result = response.json()

        reply = result.get("response", "").strip()

        if not reply:
            return (
                "I received the disease information, but I couldn't "
                "generate an explanation right now."
            )

        return reply

    except requests.exceptions.ConnectionError:
        return (
            "⚠️ Agribot's AI assistant is currently unavailable. "
            "Please make sure Ollama is running on your computer."
        )

    except requests.exceptions.Timeout:
        return (
            "⚠️ The AI assistant took too long to respond. "
            "Please try your question again."
        )

    except requests.exceptions.RequestException as e:
        print("❌ Ollama request error:", str(e))

        return (
            "⚠️ I couldn't connect to the local AI assistant. "
            "Please try again."
        )

    except Exception as e:
        print("❌ Qwen error:", str(e))

        return (
            "⚠️ Something went wrong while generating the response."
        )


# =============================================================================
# PLANT DETECTION
# =============================================================================

def detect_plant_from_message(message):
    """
    Identify plant from the farmer's message.

    Example:
        "This is a tomato leaf"
        -> tomato
    """

    if not message:
        return None

    message_lower = message.lower()

    for key, label in SUPPORTED_PLANTS.items():

        label_lower = label.lower()

        # Main plant name
        main_word = label_lower.split(" (")[0].strip()

        if main_word in message_lower:
            return key

        # Dataset key
        if key.lower() in message_lower:
            return key

        # Complete label
        if label_lower in message_lower:
            return key

    return None


# =============================================================================
# DISEASE DETECTION
# =============================================================================

def predict_disease(image_path, message=""):
    """
    Run the CNN disease model.

    IMPORTANT:
    This function is the ONLY component that decides the disease.

    Qwen never receives the image and never performs disease
    classification.
    """

    # ---------------------------------------------------------
    # Determine plant
    # ---------------------------------------------------------

    plant_key = detect_plant_from_message(message)

    if not plant_key:
        return {
            "success": False,
            "error": (
                "Please mention the plant name along with the image. "
                "For example: 'This is a tomato plant.'"
            )
        }

    # ---------------------------------------------------------
    # Load CNN
    # ---------------------------------------------------------

    model = load_disease_model()

    # ---------------------------------------------------------
    # Preprocess image
    # ---------------------------------------------------------

    img = preprocess_image(image_path)

    # ---------------------------------------------------------
    # CNN prediction
    # ---------------------------------------------------------

    prediction = model.predict(img, verbose=0)[0]

    # ---------------------------------------------------------
    # Convert prediction to plant-specific result
    # ---------------------------------------------------------

    prediction_summary = get_plant_prediction_summary(
        prediction,
        plant_key
    )

    # ---------------------------------------------------------
    # Determine disease
    # ---------------------------------------------------------

    if prediction_summary:

        disease_name = prediction_summary["best_name"]

        HEALTHY_CONFIDENCE_FLOOR = 0.78
        DISEASE_CONFIDENCE_FLOOR = 0.18
        HEALTHY_MARGIN_FLOOR = 0.12

        # -----------------------------------------------------
        # Handle healthy prediction
        # -----------------------------------------------------

        if prediction_summary["best_is_healthy"]:

            healthy_margin = (
                prediction_summary["best_score"]
                - prediction_summary["top_disease_score"]
            )

            if (
                prediction_summary["top_disease_name"]
                and
                prediction_summary["best_score"]
                < HEALTHY_CONFIDENCE_FLOOR
                and
                prediction_summary["top_disease_score"]
                >= DISEASE_CONFIDENCE_FLOOR
                and
                healthy_margin
                <= HEALTHY_MARGIN_FLOOR
            ):

                disease_name = (
                    f"Possible "
                    f"{prediction_summary['top_disease_name']}"
                )

            else:

                disease_name = (
                    f"{prediction_summary['plant_label']} Healthy"
                )

        confidence = prediction_summary["best_score"]

        plant_label = prediction_summary["plant_label"]

    # ---------------------------------------------------------
    # Fallback if plant prediction summary isn't available
    # ---------------------------------------------------------

    else:

        predicted_class = int(np.argmax(prediction))

        disease_name = get_disease_name(predicted_class)

        confidence = float(prediction[predicted_class])

        plant_label = SUPPORTED_PLANTS.get(
            plant_key,
            plant_key.title()
        )

    return {
        "success": True,
        "plant": plant_label,
        "plant_key": plant_key,
        "disease": disease_name,
        "confidence": confidence
    }


# =============================================================================
# TEXT CHAT ROUTE
# =============================================================================

@chatbot_bp.route("/chatbot", methods=["POST"])
def chatbot():

    try:

        data = request.get_json(silent=True) or {}

        message = data.get("message", "").strip()

        if not message:
            return jsonify(
                format_response(
                    "error",
                    "Please enter a message.",
                    None
                )
            ), 400

        # -----------------------------------------------------
        # Get previous CNN disease context
        # -----------------------------------------------------

        context = get_disease_context()

        plant = None
        disease = None
        confidence = None

        if context:

            plant = context.get("plant")
            disease = context.get("disease")
            confidence = context.get("confidence")

        # -----------------------------------------------------
        # Ask Qwen
        # -----------------------------------------------------

        reply = ask_qwen(
            user_message=message,
            plant=plant,
            disease=disease,
            confidence=confidence
        )

        increment_metric("chatbot_interactions")

        return jsonify(
            format_response(
                "success",
                "Chatbot response",
                reply
            )
        )

    except Exception as e:

        print("❌ Chatbot error:", str(e))

        return jsonify(
            format_response(
                "error",
                "Unable to process chatbot request.",
                None
            )
        ), 500


# =============================================================================
# IMAGE + CNN + QWEN ROUTE
# =============================================================================

@chatbot_bp.route("/chatbot/image", methods=["POST"])
def chatbot_image():

    """
    Flow:

        Farmer uploads image
                ↓
        CNN predicts disease
                ↓
        Disease + confidence stored
                ↓
        Qwen receives result
                ↓
        Qwen explains disease
    """

    temp_path = None

    try:

        # -----------------------------------------------------
        # Validate image
        # -----------------------------------------------------

        if "image" not in request.files:

            return jsonify(
                format_response(
                    "error",
                    "No image file provided.",
                    None
                )
            ), 400

        image_file = request.files["image"]

        if image_file.filename == "":

            return jsonify(
                format_response(
                    "error",
                    "Empty filename.",
                    None
                )
            ), 400

        # -----------------------------------------------------
        # Farmer's optional message
        # -----------------------------------------------------

        message = request.form.get("message", "").strip()

        # -----------------------------------------------------
        # Save temporary image
        # -----------------------------------------------------

        upload_dir = os.path.join(
            BASE_DIR,
            "static",
            "uploads"
        )

        os.makedirs(upload_dir, exist_ok=True)

        ext = os.path.splitext(
            image_file.filename
        )[1].lower() or ".jpg"

        temp_path = os.path.join(
            upload_dir,
            f"chat_{uuid.uuid4().hex}{ext}"
        )

        image_file.save(temp_path)

        # -----------------------------------------------------
        # CNN DISEASE DETECTION
        # -----------------------------------------------------

        result = predict_disease(
            temp_path,
            message
        )

        if not result["success"]:

            return jsonify(
                format_response(
                    "error",
                    result["error"],
                    None
                )
            ), 400

        # -----------------------------------------------------
        # Extract CNN result
        # -----------------------------------------------------

        plant = result["plant"]

        disease = result["disease"]

        confidence = result["confidence"]

        # -----------------------------------------------------
        # SAVE DISEASE CONTEXT
        # -----------------------------------------------------

        save_disease_context(
            plant=plant,
            disease=disease,
            confidence=confidence
        )

        # -----------------------------------------------------
        # Ask Qwen to explain CNN result
        # -----------------------------------------------------

        qwen_message = message

        if not qwen_message:

            qwen_message = (
                "Explain the detected condition, its causes, "
                "symptoms, treatment or management, and prevention."
            )

        reply = ask_qwen(
            user_message=qwen_message,
            plant=plant,
            disease=disease,
            confidence=confidence
        )

        increment_metric("chatbot_interactions")

        # -----------------------------------------------------
        # Return both CNN result and Qwen response
        # -----------------------------------------------------

        response_data = {
            "plant": plant,
            "disease": disease,
            "confidence": round(
                float(confidence) * 100,
                2
            ),
            "reply": reply
        }

        return jsonify(
            format_response(
                "success",
                "Image analysed successfully.",
                response_data
            )
        )

    except Exception as e:

        print("❌ Image chatbot error:", str(e))

        return jsonify(
            format_response(
                "error",
                "Failed to analyse the image.",
                None
            )
        ), 500

    finally:

        # -----------------------------------------------------
        # Delete temporary image
        # -----------------------------------------------------

        if temp_path and os.path.exists(temp_path):

            try:
                os.remove(temp_path)

            except Exception as cleanup_error:

                print(
                    "⚠️ Could not delete temporary image:",
                    cleanup_error
                )


# =============================================================================
# CLEAR CHAT / DISEASE CONTEXT
# =============================================================================

@chatbot_bp.route("/chatbot/clear", methods=["POST"])
def clear_chatbot_context():

    try:

        clear_disease_context()

        return jsonify(
            format_response(
                "success",
                "Chatbot context cleared.",
                None
            )
        )

    except Exception as e:

        print(
            "❌ Clear chatbot context error:",
            str(e)
        )

        return jsonify(
            format_response(
                "error",
                "Could not clear chatbot context.",
                None
            )
        ), 500