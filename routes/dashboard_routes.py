from flask import Blueprint, jsonify, session

from routes.auth_routes import load_users
from utils.metrics_store import build_recent_trends, load_metrics
from utils.response_utils import format_response

dashboard_bp = Blueprint("dashboard", __name__)


def get_user_status_counts():
    users = load_users()
    regular_users = [user for user in users if user.get("role", "user") == "user"]

    total_users = len(regular_users)
    pending_users = sum(1 for user in regular_users if user.get("status", "active") == "pending")
    restricted_users = sum(1 for user in regular_users if user.get("status", "active") == "restricted")

    return {
        "total_users": total_users,
        "pending_users": pending_users,
        "restricted_users": restricted_users
    }


@dashboard_bp.route("/api/dashboard/user-metrics", methods=["GET"])
def user_metrics():
    metrics = load_metrics()
    counts = get_user_status_counts()

    return jsonify({
        "status": "success",
        "data": {
            "total_predictions": metrics["counters"].get("predictions", 0),
            "total_registered_users": counts["total_users"],
            "disease_scans_performed": metrics["counters"].get("disease_scans", 0),
            "chatbot_interactions": metrics["counters"].get("chatbot_interactions", 0)
        }
    })


@dashboard_bp.route("/api/dashboard/admin-metrics", methods=["GET"])
def admin_metrics():
    if not session.get("user") or session["user"].get("role") != "admin":
        return jsonify(format_response("error", "Admin access required.", None)), 403

    counts = get_user_status_counts()
    trends = build_recent_trends()

    return jsonify({
        "status": "success",
        "data": {
            **counts,
            "activity_labels": trends["labels"],
            "activity_series": trends["activity_series"],
            "login_series": trends["login_series"]
        }
    })
