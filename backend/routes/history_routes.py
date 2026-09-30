import json

from flask import Blueprint, jsonify, session

from database import get_db

history = Blueprint("history", __name__, url_prefix="/api")


def authenticated():
    return session.get("user_id") is not None


def row_json(row):
    item = dict(row)
    item["explanations"] = json.loads(item.pop("explanation_json"))
    item.pop("input_json", None)
    return item


@history.get("/history")
def list_history():
    if not authenticated():
        return jsonify({"error": "Sign in to view your saved analysis history."}), 401
    rows = get_db().execute("SELECT * FROM predictions WHERE user_id = ? ORDER BY created_at DESC LIMIT 200", (session["user_id"],)).fetchall()
    return jsonify([row_json(row) for row in rows])


@history.get("/history/<int:prediction_id>")
def get_history_item(prediction_id):
    if not authenticated():
        return jsonify({"error": "Sign in to view your saved analysis history."}), 401
    row = get_db().execute("SELECT * FROM predictions WHERE id = ? AND user_id = ?", (prediction_id, session["user_id"])).fetchone()
    if not row:
        return jsonify({"error": "Analysis not found."}), 404
    item = row_json(row)
    item["input"] = json.loads(row["input_json"])
    return jsonify(item)


@history.get("/dashboard/stats")
def dashboard_stats():
    if not authenticated():
        return jsonify({"error": "Sign in to view your dashboard."}), 401
    rows = get_db().execute("SELECT prediction, risk_level, COUNT(*) AS count FROM predictions WHERE user_id = ? GROUP BY prediction, risk_level", (session["user_id"],)).fetchall()
    total = sum(row["count"] for row in rows)
    fake = sum(row["count"] for row in rows if row["prediction"] == "FAKE")
    return jsonify({"total": total, "fake": fake, "real": total - fake, "high_risk": sum(row["count"] for row in rows if row["risk_level"] == "HIGH")})
