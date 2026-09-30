import argparse
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_DIR, MODEL_DIR, MODEL_PATH, METRICS_PATH
from ml.preprocess import JobPostingVectorizer, prepare_records

def evaluate(y_true, y_pred):
    matrix = confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist()
    return {"accuracy": round(float(accuracy_score(y_true, y_pred)), 4), "fake_precision": round(float(precision_score(y_true, y_pred, pos_label=1, zero_division=0)), 4), "fake_recall": round(float(recall_score(y_true, y_pred, pos_label=1, zero_division=0)), 4), "fake_f1": round(float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)), 4), "confusion_matrix_labels": ["REAL", "FAKE"], "confusion_matrix": matrix}

def make_pipeline(classifier):
    return Pipeline([("features", JobPostingVectorizer()), ("classifier", classifier)])

def train(data_path=None):
    path = Path(data_path) if data_path else DATA_DIR / "fake_job_postings.csv"
    if not path.exists():
        raise FileNotFoundError(f"Training CSV not found: {path}")
    frame = pd.read_csv(path, keep_default_na=False, low_memory=False)
    if "fraudulent" not in frame.columns:
        raise ValueError("Dataset must contain a 'fraudulent' target column (0=real, 1=fake).")
    labels = pd.to_numeric(frame["fraudulent"], errors="coerce")
    valid = labels.isin([0, 1])
    frame = frame.loc[valid].drop(columns=["fraudulent"], errors="ignore")
    labels = labels.loc[valid].astype(int).to_numpy()
    if len(np.unique(labels)) != 2 or min(np.bincount(labels)) < 4:
        raise ValueError("Training data must contain at least four examples in each label class.")
    records = frame.to_dict(orient="records")
    features = prepare_records(records)
    train_x, test_x, train_y, test_y = train_test_split(features, labels, test_size=0.2, random_state=42, stratify=labels)
    candidates = {
        "Logistic Regression": LogisticRegression(max_iter=2000, class_weight="balanced", solver="liblinear", random_state=42),
        "Multinomial Naive Bayes": MultinomialNB(alpha=0.3),
        "Calibrated Linear SVM": CalibratedClassifierCV(estimator=LinearSVC(class_weight="balanced", random_state=42), method="sigmoid", cv=3),
    }
    comparisons, fitted, holdout_predictions = [], {}, {}
    for name, classifier in candidates.items():
        pipeline = make_pipeline(classifier)
        pipeline.fit(train_x, train_y)
        predictions = pipeline.predict(test_x)
        metrics = evaluate(test_y, predictions)
        metrics["model"] = name
        comparisons.append(metrics)
        fitted[name] = pipeline
        holdout_predictions[name] = predictions
        print(f"{name}: fake precision={metrics['fake_precision']:.3f}, recall={metrics['fake_recall']:.3f}, F1={metrics['fake_f1']:.3f}, accuracy={metrics['accuracy']:.3f}")
    winner = max(comparisons, key=lambda item: (item["fake_f1"], item["fake_precision"], item["fake_recall"]))
    selected = winner["model"]
    final_pipeline = make_pipeline(candidates[selected])
    final_pipeline.fit(features, labels)
    metrics_doc = {"dataset": path.name, "dataset_rows": int(len(labels)), "class_counts": {"REAL": int((labels == 0).sum()), "FAKE": int((labels == 1).sum())}, "selection_metric": "fake-class F1 on stratified 20% holdout", "holdout_results": comparisons, "selected_model": selected, "selected_holdout_metrics": winner, "classification_report": classification_report(test_y, holdout_predictions[selected], target_names=["REAL", "FAKE"], output_dict=True, zero_division=0)}
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": final_pipeline, "selected_model": selected, "metrics": metrics_doc, "positive_label": 1}, MODEL_PATH, compress=3)
    METRICS_PATH.write_text(json.dumps(metrics_doc, indent=2), encoding="utf-8")
    print(f"Selected: {selected} (fake F1={winner['fake_f1']:.3f}); saved to {MODEL_PATH}")
    return metrics_doc

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the fake job posting classifier.")
    parser.add_argument("--data", help="CSV with a fraudulent column; defaults to backend/data/fake_job_postings.csv")
    args = parser.parse_args()
    train(args.data)
