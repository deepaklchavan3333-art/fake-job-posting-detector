import json
from functools import lru_cache

import joblib

from config import MODEL_PATH
from ml.preprocess import prepare_records


@lru_cache(maxsize=1)
def load_model(path=None):
    model_path = path or str(MODEL_PATH)
    return joblib.load(model_path)


def explain_indicators(record):
    text = " ".join(str(record.get(key) or "") for key in ("description", "requirements", "benefits", "company_profile")).lower()
    indicators = []
    checks = [
        (not str(record.get("company_profile") or "").strip(), "Company profile was not provided"),
        (not str(record.get("salary_range") or "").strip(), "Salary range was not provided"),
        (len(str(record.get("description") or "").strip()) < 100, "Job description is unusually brief"),
        (any(term in text for term in ("telegram", "whatsapp", "signal app")), "Messaging app is mentioned for recruiting contact"),
        (any(term in text for term in ("pay upfront", "application fee", "onboarding fee", "purchase equipment")), "Upfront payment or purchase is mentioned"),
        (any(term in text for term in ("bank details", "banking information", "social security number")), "Sensitive financial or identity information is mentioned"),
    ]
    indicators.extend(label for found, label in checks if found)
    if not indicators:
        indicators.append("No common supporting warning indicators found")
    return indicators


def predict_many(records):
    artifact = load_model()
    model = artifact["pipeline"] if isinstance(artifact, dict) else artifact
    probabilities = model.predict_proba(prepare_records(records))
    classes = list(model.classes_)
    output = []
    for record, row in zip(records, probabilities):
        fake_probability = float(row[classes.index(1)])
        is_fake = fake_probability >= 0.5
        output.append({
            "prediction": "FAKE" if is_fake else "REAL",
            "fake_probability": round(fake_probability, 6),
            "confidence": round(fake_probability if is_fake else 1 - fake_probability, 6),
            "risk_level": "HIGH" if fake_probability >= 0.75 else "MEDIUM" if fake_probability >= 0.4 else "LOW",
            "explanations": explain_indicators(record),
            "notice": "Model estimate for screening only; supporting indicators are simple checks, not model feature attribution.",
        })
    return output


def predict(record):
    return predict_many([record])[0]
