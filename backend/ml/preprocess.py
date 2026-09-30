import html
import re
import numpy as np
from scipy.sparse import hstack
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer

TEXT_FIELDS = ("title", "company_profile", "location", "department", "salary_range", "description", "requirements", "benefits", "employment_type", "required_experience", "required_education", "industry", "function")
MISSING_FIELDS = ("company_profile", "salary_range", "requirements", "benefits", "employment_type", "required_experience", "required_education")
CATEGORICAL_FIELDS = ("employment_type", "required_experience", "required_education", "industry", "function", "department")
BOOLEAN_FIELDS = ("telecommuting", "has_company_logo", "has_questions")

def clean_text(value):
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()

def _bool(value):
    if isinstance(value, str):
        return int(value.strip().lower() in {"1", "true", "yes", "y"})
    try:
        return int(float(value or 0) != 0)
    except (TypeError, ValueError):
        return 0

def prepare_records(records):
    """Shared train/inference preprocessing. Returns combined text and structured metadata."""
    prepared = []
    for raw in records:
        values = {field: clean_text(raw.get(field, "")) for field in TEXT_FIELDS}
        labelled = " ".join(f"{field.replace('_', ' ')}: {values[field]}" for field in TEXT_FIELDS if values[field])
        structured = {f"missing_{field}": int(not values[field]) for field in MISSING_FIELDS}
        structured.update({f"flag_{field}": _bool(raw.get(field)) for field in BOOLEAN_FIELDS})
        structured["description_chars"] = min(len(values["description"]), 20000)
        structured["requirements_chars"] = min(len(values["requirements"]), 10000)
        structured["profile_chars"] = min(len(values["company_profile"]), 10000)
        structured["description_exclamation_count"] = min(values["description"].count("!"), 20)
        for field in CATEGORICAL_FIELDS:
            category = values[field]
            if category:
                structured[f"category_{field}_{category[:80]}"] = 1
        prepared.append({"combined_text": labelled, "structured": structured})
    return prepared

class JobPostingVectorizer(BaseEstimator, TransformerMixin):
    def __init__(self, max_features=50000, min_df=2, ngram_max=2):
        self.max_features = max_features
        self.min_df = min_df
        self.ngram_max = ngram_max

    def fit(self, X, y=None):
        self.text_vectorizer_ = TfidfVectorizer(max_features=self.max_features, min_df=self.min_df, ngram_range=(1, self.ngram_max), sublinear_tf=True, strip_accents="unicode")
        self.meta_vectorizer_ = DictVectorizer(sparse=True)
        self.text_vectorizer_.fit([row["combined_text"] for row in X])
        self.meta_vectorizer_.fit([row["structured"] for row in X])
        return self

    def transform(self, X):
        text_matrix = self.text_vectorizer_.transform([row["combined_text"] for row in X])
        meta_matrix = self.meta_vectorizer_.transform([row["structured"] for row in X])
        return hstack((text_matrix, meta_matrix), format="csr", dtype=np.float32)
