import json
import os
from functools import wraps

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from utils.metrics_store import increment_metric
from utils.response_utils import format_response

auth_bp = Blueprint("auth", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
DEFAULT_ADMIN = {
    "name": "Admin",
    "city": "System",
    "email": "admin@agribot.local",
    "username": "admin",
    "password_hash": generate_password_hash("Admin@123"),
    "role": "admin",
    "status": "active"
}


def ensure_user_store():
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(USERS_FILE):
        return

    with open(USERS_FILE, "w", encoding="utf-8") as file:
        json.dump([DEFAULT_ADMIN], file, indent=2)


def load_users():
    ensure_user_store()

    with open(USERS_FILE, "r", encoding="utf-8") as file:
        users = json.load(file)

    updated = False

    for user in users:
        if "role" not in user:
            user["role"] = "user"
            updated = True

        if "status" not in user:
            user["status"] = "active"
            updated = True

    if updated:
        save_users(users)

    return users


def save_users(users):
    ensure_user_store()

    with open(USERS_FILE, "w", encoding="utf-8") as file:
        json.dump(users, file, indent=2)


def normalize_user(user):
    return {
        "name": user["name"],
        "city": user["city"],
        "email": user["email"],
        "username": user["username"],
        "role": user.get("role", "user"),
        "status": user.get("status", "active")
    }


def validate_registration_payload(data):
    required_fields = ["name", "city", "email", "username", "password"]

    for field in required_fields:
        value = str(data.get(field, "")).strip()
        if not value:
            return f"{field.capitalize()} is required."

    email = data["email"].strip()
    password = data["password"]

    if "@" not in email or "." not in email:
        return "Please enter a valid email address."

    has_upper = any(char.isupper() for char in password)
    has_lower = any(char.islower() for char in password)
    has_digit = any(char.isdigit() for char in password)
    has_symbol = any(not char.isalnum() for char in password)

    if len(password) < 8 or not (has_upper and has_lower and has_digit and has_symbol):
        return "Password must be at least 8 characters and include upper, lower, number, and symbol."

    return None


def login_required(role=None):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            user = session.get("user")

            if not user:
                return None

            if role and user.get("role") != role:
                return None

            return view_func(*args, **kwargs)

        return wrapped_view

    return decorator


@auth_bp.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json() or {}
        validation_error = validate_registration_payload(data)

        if validation_error:
            return jsonify(format_response("error", validation_error, None)), 400

        users = load_users()
        email = data["email"].strip().lower()
        username = data["username"].strip().lower()

        for user in users:
            if user["email"].lower() == email:
                return jsonify(format_response("error", "A user with this email already exists.", None)), 409

            if user["username"].lower() == username:
                return jsonify(format_response("error", "Username already exists.", None)), 409

        users.append({
            "name": data["name"].strip(),
            "city": data["city"].strip(),
            "email": email,
            "username": username,
            "password_hash": generate_password_hash(data["password"]),
            "role": "user",
            "status": "active"
        })

        save_users(users)
        increment_metric("registrations")

        return jsonify(format_response("success", "User registered successfully. Please log in.", None))

    except Exception as error:
        return jsonify(format_response("error", str(error), None)), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json() or {}
        username = str(data.get("username", "")).strip().lower()
        password = str(data.get("password", ""))
        expected_role = str(data.get("expected_role", "user")).strip().lower()

        if not username or not password:
            return jsonify(format_response("error", "Username and password are required.", None)), 400

        if expected_role not in {"user", "admin"}:
            expected_role = "user"

        users = load_users()

        for user in users:
            if user["username"].lower() != username:
                continue

            if user.get("status", "active") == "restricted":
                return jsonify(format_response("error", "This account is restricted. Please contact admin.", None)), 403

            if not check_password_hash(user["password_hash"], password):
                break

            safe_user = normalize_user(user)

            if safe_user["role"] != expected_role:
                mismatch_message = "Use the admin login page." if safe_user["role"] == "admin" else "Use the user login page."
                return jsonify(format_response("error", mismatch_message, None)), 403

            session["user"] = safe_user
            session.permanent = True
            increment_metric("logins")

            redirect_to = "/admin-dashboard" if safe_user["role"] == "admin" else "/user-dashboard"

            return jsonify({
                "status": "success",
                "message": "Login successful.",
                "role": safe_user["role"],
                "redirect_to": redirect_to,
                "user": safe_user
            })

        return jsonify(format_response("error", "Invalid username or password.", None)), 401

    except Exception as error:
        return jsonify(format_response("error", str(error), None)), 500


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify(format_response("success", "Logged out successfully.", None))


@auth_bp.route("/session", methods=["GET"])
def get_session():
    user = session.get("user")

    if not user:
        return jsonify(format_response("error", "No active session.", None)), 401

    return jsonify({
        "status": "success",
        "message": "Active session found.",
        "data": user
    })
