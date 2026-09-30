from flask import Flask, jsonify, request
from flask_cors import CORS
from urllib.parse import urlencode, quote
import os
import re
import requests
import time
import json
import feedparser
from config import FRONTEND_ORIGINS, METRICS_PATH, SECRET_KEY, MODEL_PATH, SESSION_COOKIE_SECURE
from database import init_app as init_database
from database.schema import init_db
from routes.auth_routes import auth
from routes.history_routes import history
from routes.prediction_routes import predictions
from services.prediction_service import predict, predict_many

app = Flask(__name__)
app.config.update(SECRET_KEY=SECRET_KEY, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=SESSION_COOKIE_SECURE)
CORS(app, origins=FRONTEND_ORIGINS, supports_credentials=True)
init_database(app)
with app.app_context():
    init_db()
app.register_blueprint(auth)
app.register_blueprint(history)
app.register_blueprint(predictions)

DEMO_JOBS = [
    {"id": 1, "company": "Northstar Labs", "mark": "N", "color": "violet", "title": "Product Designer", "location": "Remote · US", "salary": "$115k – $145k", "posted": "2h ago", "score": None, "tags": ["Full-time", "Design"], "signal": "Demo listing · run a model check", "description": "Join our product team to shape thoughtful tools for people doing their best work. You will partner with research and engineering from discovery through launch.", "source": "Demo listing"},
    {"id": 2, "company": "BrightPath Global", "mark": "B", "color": "orange", "title": "Remote Data Entry Clerk", "location": "Work from anywhere", "salary": "$85 – $120 / hour", "posted": "38m ago", "score": None, "tags": ["Remote", "Entry level"], "signal": "Demo listing · run a model check", "description": "Easy data entry job. No experience required. Earn up to $120 hourly working just 2 hours per day. Send your details to our hiring manager on Telegram to get started immediately.", "source": "Demo listing"},
    {"id": 3, "company": "Linear", "mark": "L", "color": "ink", "title": "Customer Success Manager", "location": "New York, NY · Hybrid", "salary": "$105k – $135k", "posted": "5h ago", "score": None, "tags": ["Full-time", "Customer success"], "signal": "Demo listing · run a model check", "description": "Help our customers build healthy product development habits. You will guide teams through onboarding, share best practices, and bring product feedback back to our team.", "source": "Demo listing"},
    {"id": 4, "company": "Pinnacle Ventures", "mark": "P", "color": "blue", "title": "Executive Assistant — Crypto", "location": "Remote · Global", "salary": "$180k – $240k", "posted": "1h ago", "score": None, "tags": ["Remote", "Assistant"], "signal": "Demo listing · run a model check", "description": "Seeking a detail-oriented assistant. Successful applicants must pay a refundable $250 onboarding fee and provide banking information for payroll setup before the interview.", "source": "Demo listing"},
]

SIGNALS = [
    (35, re.compile(r"\b(telegram|whatsapp|text us|message us on)\b", re.I), "Requests contact through messaging apps"),
    (40, re.compile(r"\b(fee|pay upfront|onboarding fee|banking information|bank details)\b", re.I), "Requests money or sensitive financial details"),
    (20, re.compile(r"\b(guaranteed|no experience|easy money|earn from home)\b", re.I), "Uses unrealistic or vague promises"),
    (15, re.compile(r"\b(immediately|urgent hiring|act now)\b", re.I), "Uses high-pressure language"),
]

FEED_CACHE = {}
FEED_TTL = {"Remote OK": 1800, "Remotive": 21600}
ADZUNA_CACHE = {}

def configured_rss_jobs():
    """Read user-authorized RSS URLs from JOB_RSS_FEEDS (JSON array of {name,url})."""
    try:
        sources = json.loads(os.getenv("JOB_RSS_FEEDS", "[]"))
    except json.JSONDecodeError:
        app.logger.warning("JOB_RSS_FEEDS must be a JSON array")
        return []
    jobs = []
    for source in sources if isinstance(sources, list) else []:
        if not isinstance(source, dict):
            continue
        name, url = source.get("name", "RSS feed"), source.get("url", "")
        if not url.startswith("https://"):
            continue
        cache_key = f"rss:{name}:{url}"
        try:
            cached = FEED_CACHE.get(cache_key)
            if cached and time.time() - cached[0] < 1800:
                entries = cached[1]
            else:
                response = requests.get(url, headers={"User-Agent": "Clearhire RSS reader/1.0"}, timeout=15)
                response.raise_for_status()
                entries = feedparser.parse(response.content).entries[:50]
                FEED_CACHE[cache_key] = (time.time(), entries)
            for entry in entries:
                title = entry.get("title", "Job listing")
                description = entry.get("summary", entry.get("description", ""))
                score, signal = score_listing(description)
                jobs.append({"id": f"rss-{name}-{entry.get('id', entry.get('link', title))}", "company": entry.get("author", name), "mark": name[:1].upper(), "color": "blue", "title": title, "location": entry.get("location", "See posting"), "salary": entry.get("salary", "Salary not listed"), "posted": entry.get("published", "Recently"), "score": score, "tags": ["RSS feed"], "signal": signal, "description": description, "source": name, "url": entry.get("link", "")})
        except (requests.RequestException, ValueError, TypeError) as error:
            app.logger.warning("RSS source %s unavailable: %s", name, error)
    return jobs

def cached_feed(name, url, params=None):
    cached = FEED_CACHE.get(name)
    if cached and time.time() - cached[0] < FEED_TTL[name]:
        return cached[1]
    response = requests.get(url, params=params, headers={"User-Agent": "Clearhire job search demo"}, timeout=15)
    response.raise_for_status()
    data = response.json()
    FEED_CACHE[name] = (time.time(), data)
    return data

def normalize_public_jobs():
    jobs = []
    try:
        feed = cached_feed("Remote OK", "https://remoteok.com/api")
        for item in feed:
            if not isinstance(item, dict) or not item.get("position"):
                continue
            description = item.get("description") or ""
            score, signal = score_listing(description)
            company = item.get("company") or "Company not listed"
            jobs.append({"id": f"remoteok-{item.get('id')}", "company": company, "mark": company[:1].upper(), "color": "blue", "title": item["position"], "location": item.get("location") or "Remote", "salary": item.get("salary") or "Salary not listed", "posted": (item.get("date") or "")[:10] or "Recently", "score": score, "tags": item.get("tags") or [], "signal": signal, "description": description, "source": "Remote OK", "url": item.get("url") or ""})
    except (requests.RequestException, ValueError) as error:
        app.logger.warning("Remote OK feed unavailable: %s", error)
    try:
        feed = cached_feed("Remotive", "https://remotive.com/api/remote-jobs", {"limit": 100})
        for item in feed.get("jobs", []):
            description = item.get("description") or ""
            score, signal = score_listing(description)
            company = item.get("company_name") or "Company not listed"
            jobs.append({"id": f"remotive-{item.get('id')}", "company": company, "mark": company[:1].upper(), "color": "violet", "title": item.get("title") or "Untitled job", "location": item.get("candidate_required_location") or "Remote", "salary": item.get("salary") or "Salary not listed", "posted": (item.get("publication_date") or "")[:10] or "Recently", "score": score, "tags": [item.get("job_type") or "Remote"], "signal": signal, "description": description, "source": "Remotive", "url": item.get("url") or ""})
    except (requests.RequestException, ValueError) as error:
        app.logger.warning("Remotive feed unavailable: %s", error)
    return jobs

@app.get("/api/health")
def health():
    configured = bool(os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY"))
    try:
        metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8")) if METRICS_PATH.exists() else {}
    except (OSError, ValueError):
        metrics = {}
    return jsonify({"status": "ok", "model_ready": MODEL_PATH.exists(), "model": metrics.get("selected_model"), "live_sources": ["Remote OK", "Remotive"] + (["Adzuna"] if configured else []), "message": "Public feeds enabled; Adzuna requires API credentials."})

def score_listing(description):
    score, found = 0, []
    for weight, pattern, label in SIGNALS:
        if pattern.search(description or ""):
            score += weight
            found.append(label)
    if len((description or "").strip()) < 100:
        score += 10
        found.append("Very short description")
    score = min(score, 100)
    return score, "; ".join(found) if found else "No common warning signs detected"

def get_adzuna_jobs(what, where, country):
    app_id, app_key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return None
    country = re.sub(r"[^a-z]", "", country.lower())[:2] or "in"
    cache_key = (country, what.lower(), where.lower())
    cached = ADZUNA_CACHE.get(cache_key)
    if cached and time.time() - cached[0] < 1800:
        return cached[1]
    params = {"app_id": app_id, "app_key": app_key, "results_per_page": 20, "content-type": "application/json"}
    if what: params["what"] = what[:120]
    if where: params["where"] = where[:120]
    response = requests.get(f"https://api.adzuna.com/v1/api/jobs/{country}/search/1", params=params, timeout=12)
    response.raise_for_status()
    jobs = []
    for item in response.json().get("results", []):
        description = item.get("description", "")
        score, signal = score_listing(description)
        company = (item.get("company") or {}).get("display_name") or "Company not listed"
        location = (item.get("location") or {}).get("display_name") or "Location not listed"
        low, high = item.get("salary_min"), item.get("salary_max")
        salary = f"{low:,.0f} – {high:,.0f}" if low and high else "Salary not listed"
        category = (item.get("category") or {}).get("label", "Job")
        jobs.append({"id": item.get("id") or item.get("redirect_url"), "company": company, "mark": company[:1].upper(), "color": "blue", "title": item.get("title") or "Untitled job", "location": location, "salary": salary, "posted": item.get("created", "")[:10] or "Recently", "score": score, "tags": [category], "signal": signal, "description": description, "source": "Adzuna", "url": item.get("redirect_url", "")})
    ADZUNA_CACHE[cache_key] = (time.time(), jobs)
    return jobs

@app.get("/api/jobs")
def get_jobs():
    what = request.args.get("what", "").strip()
    where = request.args.get("where", "").strip()
    country = request.args.get("country", "in")
    source_filter = request.args.get("source", "All sources")
    kind_filter = request.args.get("kind", "All types")
    mode_filter = request.args.get("mode", "Any location")
    age_filter = request.args.get("age", "Any time")
    try:
        jobs = normalize_public_jobs() + configured_rss_jobs()
    except Exception as error:
        app.logger.warning("Public job feeds unavailable: %s", error)
        jobs = []
    try:
        adzuna_jobs = get_adzuna_jobs(what, where, country)
        if adzuna_jobs:
            jobs.extend(adzuna_jobs)
    except requests.RequestException as error:
        app.logger.warning("Adzuna request failed: %s", error)
    if not jobs:
        jobs = DEMO_JOBS.copy()
    filtered = []
    for job in jobs:
        haystack = f"{job['title']} {job['company']} {job['location']} {' '.join(job.get('tags', []))} {job.get('description', '')}".lower()
        if what and what.lower() not in haystack:
            continue
        if where and where.lower() not in f"{job['location']} {job['company']}".lower():
            continue
        if source_filter != "All sources" and job.get("source") != source_filter:
            continue
        if kind_filter != "All types" and kind_filter.lower() not in f"{' '.join(job.get('tags', []))} {job['title']}".lower():
            continue
        is_remote = "remote" in f"{job['location']} {' '.join(job.get('tags', []))}".lower()
        if mode_filter == "Remote" and not is_remote:
            continue
        if mode_filter == "On-site / hybrid" and is_remote:
            continue
        if age_filter != "Any time":
            from datetime import datetime, timedelta, timezone
            cutoff = datetime.now(timezone.utc) - timedelta(days=int(age_filter))
            try:
                posted = datetime.fromisoformat(job.get("posted", "").replace("Z", "+00:00"))
                if posted.tzinfo is None: posted = posted.replace(tzinfo=timezone.utc)
                if posted < cutoff: continue
            except (ValueError, TypeError):
                relative = re.search(r"(\d+)\s*(minute|hour|day|week)s?", job.get("posted", ""), re.I)
                if relative:
                    amount = int(relative.group(1))
                    unit = relative.group(2).lower()
                    posted_age = amount / 1440 if unit == "minute" else amount / 24 if unit == "hour" else amount * 7 if unit == "week" else amount
                    if posted_age > int(age_filter): continue
        filtered.append(job)
    if filtered and MODEL_PATH.exists():
        try:
            records = [{"title": job.get("title", ""), "company_profile": job.get("company", ""), "location": job.get("location", ""), "salary_range": job.get("salary", ""), "description": job.get("description", "")} for job in filtered]
            estimates = predict_many(records)
            for job, estimate in zip(filtered, estimates):
                job["score"] = estimate["fake_percent"] if "fake_percent" in estimate else round(estimate["fake_probability"] * 100)
                job["prediction"] = estimate["prediction"]
                job["confidence"] = estimate["confidence"]
                job["signal"] = f"Model estimate · {estimate['prediction'].lower()} ({round(estimate['confidence'] * 100)}% confidence)"
        except Exception as error:
            app.logger.warning("Could not score a feed batch: %s", error)
            for job in filtered:
                job["score"] = None
                job["signal"] = "Model estimate unavailable for this listing"
    else:
        for job in filtered:
            job["score"] = None
            job["signal"] = "Model not trained · run a model check"
    return jsonify(filtered)

@app.get("/api/board-links")
def board_links():
    what, where = request.args.get("what", ""), request.args.get("where", "")
    return jsonify({"Indeed": "https://in.indeed.com/jobs?" + urlencode({"q": what, "l": where}), "Naukri": "https://www.naukri.com/" + quote((what or "jobs").replace(" ", "-")) + "-jobs" + ("?l=" + quote(where) if where else ""), "LinkedIn": "https://www.linkedin.com/jobs/search/?" + urlencode({"keywords": what, "location": where})})

@app.post("/api/analyze")
def analyze():
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "Provide a non-empty job post in the text field."}), 400
    return jsonify(predict({"description": text}))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
