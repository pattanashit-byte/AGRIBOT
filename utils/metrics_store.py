import json
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
METRICS_FILE = os.path.join(DATA_DIR, "metrics.json")

DEFAULT_METRICS = {
    "counters": {
        "predictions": 0,
        "disease_scans": 0,
        "chatbot_interactions": 0,
        "logins": 0,
        "registrations": 0
    },
    "history": []
}


def ensure_metrics_store():
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(METRICS_FILE):
        return

    with open(METRICS_FILE, "w", encoding="utf-8") as file:
        json.dump(DEFAULT_METRICS, file, indent=2)


def load_metrics():
    ensure_metrics_store()

    with open(METRICS_FILE, "r", encoding="utf-8") as file:
        metrics = json.load(file)

    counters = metrics.setdefault("counters", {})
    history = metrics.setdefault("history", [])

    for key, value in DEFAULT_METRICS["counters"].items():
        counters.setdefault(key, value)

    metrics["history"] = history
    return metrics


def save_metrics(metrics):
    ensure_metrics_store()

    with open(METRICS_FILE, "w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2)


def increment_metric(metric_name, amount=1, when=None):
    metrics = load_metrics()
    counters = metrics["counters"]

    if metric_name not in counters:
        counters[metric_name] = 0

    counters[metric_name] += amount

    stamp = when or datetime.now()
    day_key = stamp.strftime("%Y-%m-%d")

    entry = next((item for item in metrics["history"] if item["date"] == day_key), None)

    if entry is None:
        entry = {
            "date": day_key,
            "predictions": 0,
            "disease_scans": 0,
            "chatbot_interactions": 0,
            "logins": 0,
            "registrations": 0
        }
        metrics["history"].append(entry)

    entry[metric_name] = entry.get(metric_name, 0) + amount
    save_metrics(metrics)


def build_recent_trends(days=10):
    metrics = load_metrics()
    history_index = {item["date"]: item for item in metrics["history"]}
    today = datetime.now().date()

    labels = []
    activity_series = []
    login_series = []

    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        key = day.strftime("%Y-%m-%d")
        entry = history_index.get(key, {})

        labels.append(day.strftime("%b %d"))
        activity_series.append(
            entry.get("predictions", 0)
            + entry.get("disease_scans", 0)
            + entry.get("chatbot_interactions", 0)
        )
        login_series.append(entry.get("logins", 0))

    return {
        "labels": labels,
        "activity_series": activity_series,
        "login_series": login_series
    }
