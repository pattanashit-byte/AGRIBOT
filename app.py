from datetime import timedelta

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

app.register_blueprint(crop_bp)
app.register_blueprint(disease_bp)
app.register_blueprint(chatbot_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)

PROTECTED_ENDPOINTS = {
    "home",
    "upload_page",
    "chat_page",
    "user_dashboard",
    "admin_dashboard",
    "crop.predict_crop",
    "disease.predict_disease",
    "chatbot.chatbot",
    "dashboard.user_metrics",
    "dashboard.admin_metrics"
}
API_ENDPOINTS = {
    "crop.predict_crop",
    "disease.predict_disease",
    "chatbot.chatbot",
    "dashboard.user_metrics",
    "dashboard.admin_metrics"
}
ADMIN_ENDPOINTS = {"admin_dashboard", "dashboard.admin_metrics"}


@app.before_request
def protect_routes():
    if request.endpoint is None:
        return None

    if request.endpoint not in PROTECTED_ENDPOINTS:
        return None

    user = session.get("user")

    if not user:
        if request.endpoint in API_ENDPOINTS:
            return jsonify(format_response("error", "Authentication required.", None)), 401
        if request.endpoint in ADMIN_ENDPOINTS:
            return redirect(url_for("admin_login_page"))
        return redirect(url_for("login_page"))

    if request.endpoint == "user_dashboard" and user.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))

    if request.endpoint in ADMIN_ENDPOINTS and user.get("role") != "admin":
        if request.endpoint in API_ENDPOINTS:
            return jsonify(format_response("error", "Admin access required.", None)), 403
        return redirect(url_for("user_dashboard"))

    return None


@app.context_processor
def inject_auth_context():
    return {
        "current_user": session.get("user"),
        "is_authenticated": bool(session.get("user"))
    }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload")
def upload_page():
    return render_template("upload.html", supported_plants=get_supported_plant_options())


@app.route("/chat")
@app.route("/chatbot")
def chat_page():
    return render_template("chatbot.html")


@app.route("/login")
def login_page():
    if session.get("user"):
        if session["user"].get("role") == "admin":
            return redirect(url_for("admin_dashboard"))

        return redirect(url_for("user_dashboard"))

    return render_template("login.html")


@app.route("/admin-login")
def admin_login_page():
    if session.get("user"):
        if session["user"].get("role") == "admin":
            return redirect(url_for("admin_dashboard"))

        return redirect(url_for("user_dashboard"))

    return render_template("admin_login.html")


@app.route("/register")
def register_page():
    if session.get("user"):
        if session["user"].get("role") == "admin":
            return redirect(url_for("admin_dashboard"))

        return redirect(url_for("user_dashboard"))

    return render_template("register.html")


@app.route("/user-dashboard")
def user_dashboard():
    return render_template("dashboard_user.html")


@app.route("/result")
def result_page():
    if session.get("user"):
        if session["user"].get("role") == "admin":
            return redirect(url_for("admin_dashboard"))

        return redirect(url_for("user_dashboard"))

    return redirect(url_for("login_page"))


@app.route("/admin")
@app.route("/admin-dashboard")
def admin_dashboard():
    return render_template("dashboard_admin.html")


if __name__ == "__main__":
    app.run(debug=True)
