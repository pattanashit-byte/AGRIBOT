from datetime import timedelta

import requests

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS

from routes.auth_routes import auth_bp
from routes.chatbot_routes import chatbot_bp
from routes.crop_routes import crop_bp
from routes.dashboard_routes import dashboard_bp
from routes.disease_routes import disease_bp
from utils.disease_labels import get_supported_plant_options
from utils.response_utils import format_response


app = Flask(__name__)

app.config["SECRET_KEY"] = "agribot-liquid-glass-secret-key"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

CORS(app, supports_credentials=True)


# ============================================================
# EXISTING BLUEPRINTS
# ============================================================

app.register_blueprint(crop_bp)
app.register_blueprint(disease_bp)
app.register_blueprint(chatbot_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)


# ============================================================
# EXISTING PROTECTION CONFIGURATION
# ============================================================

PROTECTED_ENDPOINTS = {
    "upload_page",
    "chat_page",
    "user_dashboard",
    "admin_dashboard",
    "crop_prediction_page",
    "crop.predict_crop",
    "disease.predict_disease",
    "chatbot.chatbot",
    "chatbot.chatbot_image",
    "dashboard.user_metrics",
    "dashboard.admin_metrics"
}

API_ENDPOINTS = {
    "crop.predict_crop",
    "disease.predict_disease",
    "chatbot.chatbot",
    "chatbot.chatbot_image",
    "dashboard.user_metrics",
    "dashboard.admin_metrics"
}

ADMIN_ENDPOINTS = {
    "admin_dashboard",
    "dashboard.admin_metrics"
}


# ============================================================
# EXISTING AUTHENTICATION / ROUTE PROTECTION
# ============================================================

@app.before_request
def protect_routes():

    if request.endpoint is None:
        return None

    if request.endpoint not in PROTECTED_ENDPOINTS:
        return None

    user = session.get("user")

    if not user:

        if request.endpoint in API_ENDPOINTS:
            return jsonify(
                format_response(
                    "error",
                    "Authentication required.",
                    None
                )
            ), 401

        if request.endpoint in ADMIN_ENDPOINTS:
            return redirect(url_for("admin_login_page"))

        return redirect(url_for("login_page"))

    if request.endpoint == "user_dashboard" and user.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))

    if request.endpoint in ADMIN_ENDPOINTS and user.get("role") != "admin":

        if request.endpoint in API_ENDPOINTS:
            return jsonify(
                format_response(
                    "error",
                    "Admin access required.",
                    None
                )
            ), 403

        return redirect(url_for("user_dashboard"))

    return None


# ============================================================
# EXISTING TEMPLATE CONTEXT
# ============================================================

@app.context_processor
def inject_auth_context():
    return {
        "current_user": session.get("user"),
        "is_authenticated": bool(session.get("user"))
    }


# ============================================================
# NEW WEATHER API
# ============================================================

@app.route("/api/weather", methods=["GET"])
def weather():

    try:

        # ----------------------------------------------------
        # Get coordinates from frontend
        # ----------------------------------------------------

        latitude = request.args.get("latitude", type=float)
        longitude = request.args.get("longitude", type=float)

        if latitude is None or longitude is None:

            return jsonify({
                "status": "error",
                "message": "Latitude and longitude are required."
            }), 400

        # Basic coordinate validation
        if not (-90 <= latitude <= 90):

            return jsonify({
                "status": "error",
                "message": "Invalid latitude."
            }), 400

        if not (-180 <= longitude <= 180):

            return jsonify({
                "status": "error",
                "message": "Invalid longitude."
            }), 400


        # ----------------------------------------------------
        # REAL WEATHER API
        # ----------------------------------------------------

        weather_url = "https://api.open-meteo.com/v1/forecast"

        params = {

            "latitude": latitude,
            "longitude": longitude,

            # Current conditions
            "current": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "apparent_temperature,"
                "precipitation,"
                "rain,"
                "weather_code,"
                "cloud_cover,"
                "pressure_msl,"
                "wind_speed_10m,"
                "wind_gusts_10m,"
                "uv_index"
            ),

            # Hourly information
            "hourly": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "precipitation_probability,"
                "precipitation,"
                "rain,"
                "wind_speed_10m,"
                "uv_index"
            ),

            # Daily forecast
            "daily": (
                "weather_code,"
                "temperature_2m_max,"
                "temperature_2m_min,"
                "precipitation_sum,"
                "rain_sum,"
                "precipitation_probability_max,"
                "wind_speed_10m_max,"
                "uv_index_max,"
                "et0_fao_evapotranspiration"
            ),

            "timezone": "auto",

            "forecast_days": 7
        }


        response = requests.get(
            weather_url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        weather_data = response.json()


        # ----------------------------------------------------
        # Return REAL WEATHER DATA
        # ----------------------------------------------------

        return jsonify({

            "status": "success",

            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "timezone": weather_data.get("timezone")
            },

            "current": weather_data.get("current", {}),

            "hourly": weather_data.get("hourly", {}),

            "daily": weather_data.get("daily", {})

        })


    except requests.exceptions.Timeout:

        return jsonify({
            "status": "error",
            "message": "Weather service timed out. Please try again."
        }), 504


    except requests.exceptions.RequestException as e:

        print("Weather API error:", repr(e))

        return jsonify({
            "status": "error",
            "message": "Unable to retrieve live weather data."
        }), 502


    except Exception as e:

        print("Weather endpoint error:", repr(e))

        return jsonify({
            "status": "error",
            "message": "Weather service failed."
        }), 500


# ============================================================
# EXISTING HOME
# ============================================================

@app.route("/")
def home():

    user = session.get("user")

    if not user:
        return redirect(url_for("login_page"))

    if user.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))

    return redirect(url_for("user_dashboard"))


# ============================================================
# EXISTING CROP PAGE
# ============================================================

@app.route("/crop-prediction")
def crop_prediction_page():
    return render_template("index.html")


# ============================================================
# EXISTING DISEASE UPLOAD PAGE
# ============================================================

@app.route("/upload")
def upload_page():

    return render_template(
        "upload.html",
        supported_plants=get_supported_plant_options()
    )


# ============================================================
# EXISTING CHATBOT
# ============================================================

@app.route("/chat")
@app.route("/chatbot")
def chat_page():
    return render_template("chatbot.html")


# ============================================================
# EXISTING LOGIN
# ============================================================

@app.route("/login")
def login_page():

    if session.get("user"):

        if session["user"].get("role") == "admin":
            return redirect(url_for("admin_dashboard"))

        return redirect(url_for("user_dashboard"))

    return render_template("login.html")


# ============================================================
# EXISTING ADMIN LOGIN
# ============================================================

@app.route("/admin-login")
def admin_login_page():

    if session.get("user"):

        if session["user"].get("role") == "admin":
            return redirect(url_for("admin_dashboard"))

        return redirect(url_for("user_dashboard"))

    return render_template("admin_login.html")


# ============================================================
# EXISTING REGISTER
# ============================================================

@app.route("/register")
def register_page():

    if session.get("user"):

        if session["user"].get("role") == "admin":
            return redirect(url_for("admin_dashboard"))

        return redirect(url_for("user_dashboard"))

    return render_template("register.html")


# ============================================================
# EXISTING USER DASHBOARD
# ============================================================

@app.route("/user-dashboard")
def user_dashboard():
    return render_template("dashboard_user.html")


# ============================================================
# EXISTING RESULT
# ============================================================

@app.route("/result")
def result_page():

    if session.get("user"):

        if session["user"].get("role") == "admin":
            return redirect(url_for("admin_dashboard"))

        return redirect(url_for("user_dashboard"))

    return redirect(url_for("login_page"))


# ============================================================
# EXISTING ADMIN DASHBOARD
# ============================================================

@app.route("/admin")
@app.route("/admin-dashboard")
def admin_dashboard():
    return render_template("dashboard_admin.html")


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True
    )