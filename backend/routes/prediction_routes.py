import json

from flask import Blueprint, jsonify, request, session

from database import get_db
from services.prediction_service import predict
from services.url_extractor import extract_job_post

predictions = Blueprint("predictions", __name__, url_prefix="/api")
FIELDS = ("title", "location", "department", "salary_range", "company_profile", "description", "requirements", "benefits", "telecommuting", "has_company_logo", "has_questions", "employment_type", "required_experience", "required_education", "industry", "function")


def _analyze_and_save(record, company_name="", source_url=None):
    if not str(record["title"] or "").strip() and not str(record["description"] or "").strip():
        return jsonify({"error": "Provide a job title or description to analyze."}), 400
    if any(not isinstance(value, (str, bool, int, float, type(None))) for value in record.values()):
        return jsonify({"error": "Job fields must be text or simple values."}), 400
    if sum(len(str(value or "")) for value in record.values()) > 40000:
        return jsonify({"error": "The submitted listing is too long (40,000 characters maximum)."}), 413
    try:
        result = predict(record)
    except FileNotFoundError:
        return jsonify({"error": "The detection model has not been trained yet. Run the training command in the README."}), 503
    except Exception:
        from flask import current_app
        current_app.logger.exception("Model prediction failed")
        return jsonify({"error": "The model could not analyze this listing."}), 503
    probability = result["fake_probability"]
    saved_record = {**record, **({"source_url": source_url} if source_url else {})}
    if session.get("user_id"):
        db = get_db()
        cursor = db.execute("""INSERT INTO predictions (user_id, job_title, company_name, prediction, confidence, fake_probability, risk_level, input_json, explanation_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session["user_id"], str(record["title"] or "Untitled job")[:300], str(company_name or "")[:300], result["prediction"], result["confidence"], probability, result["risk_level"], json.dumps(saved_record), json.dumps(result["explanations"])))
        db.commit()
        result["id"] = cursor.lastrowid
    else:
        result["id"] = None
    result["fake_percent"] = round(probability * 100)
    if source_url:
        result["source_url"] = source_url
    return jsonify(result)


@predictions.post("/predict")
def create_prediction():
    body = request.get_json(silent=True) or {}
    record = {key: body.get(key, "") for key in FIELDS}
    return _analyze_and_save(record, body.get("company_name", ""))


@predictions.post("/analyze-url")
def analyze_url():
    body = request.get_json(silent=True) or {}
    source_url = body.get("url", "")
    if not isinstance(source_url, str) or not source_url.strip():
        return jsonify({"error": "Paste the public HTTPS URL of a job post."}), 400
    try:
        extracted = extract_job_post(source_url.strip())
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    record = {key: extracted.get(key, "") for key in FIELDS}
    response = _analyze_and_save(record, extracted.get("company_name", ""), extracted.get("source_url"))
    if isinstance(response, tuple):
        return response
    result = response.get_json()
    result["source_listing"] = extracted
    return jsonify(result)
