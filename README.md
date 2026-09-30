# Clearhire

Clearhire is a React and Flask job-posting risk screening app. It combines a TF-IDF text model with structured job-posting fields, returns an estimated fake-post probability and confidence, and can save account-owned prediction history in SQLite. The interface checks pasted text, OCR text from an uploaded poster, or a public job-post URL. The curated listing cards are removed; live feed API routes remain available for integrations.

**Live frontend:** [fake-job-posting-detectorr.netlify.app](https://fake-job-posting-detectorr.netlify.app/)

## Project layout

- `frontend/` — React + Vite user interface
- `backend/` — Flask APIs, SQLite schema, model training and inference
- `backend/data/fake_job_postings.csv` — public labeled training dataset
- `backend/models/` — generated model and holdout metrics after training

## Run locally

Use two terminals from the repository root. The backend uses Python 3.10+.

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python ml\train_model.py
python app.py
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). Vite proxies `/api` to Flask at `http://127.0.0.1:5000`. To change the backend URL, edit `frontend/vite.config.js`.

## Deployment

The React frontend is deployed to Netlify, and the Flask API runs as a separate Render web service. Netlify proxies `/api/*` requests to Render through `netlify.toml`.

1. Keep `backend/models/fake_job_model.joblib` in the repository because Render needs it to serve predictions.
2. The Render service uses root directory `backend`, build command `pip install -r requirements.txt`, and start command `gunicorn app:app --bind 0.0.0.0:$PORT`.
3. Set Render environment variables `FLASK_SECRET_KEY` to a long random secret and `SESSION_COOKIE_SECURE` to `true`. Render's default filesystem is ephemeral; use persistent storage and set `DATABASE_PATH` if prediction history must survive restarts.
4. `netlify.toml` sets the frontend base directory to `frontend`, build command to `npm run build`, publish directory to `dist`, and proxies API requests to `https://fake-job-posting-detector-fnd6.onrender.com`.
5. Check [the API health endpoint](https://fake-job-posting-detectorr.netlify.app/api/health); it should return JSON with `"model_ready": true`. Then test registration and a poster, text, or URL check on the site.

On Render's free web service plan, local SQLite files are not durable. Use a paid service with a persistent disk for this SQLite setup, or migrate the database layer to managed Postgres for a more durable deployment. See [Render's disk documentation](https://render.com/docs/disks).

The first model training run compares Logistic Regression, Multinomial Naive Bayes and calibrated Linear SVM on a stratified holdout. It selects the model using fake-class F1, then retrains that model on all labeled rows. Model training can take a few minutes. Run it again whenever you replace the training data. The APIs stay available while a model is absent, but `/api/predict` returns HTTP 503 until training completes.

Optional environment variables:

- `FLASK_SECRET_KEY` — replace the development session key for deployment
- `DATABASE_PATH` — override the default SQLite file path
- `FRONTEND_ORIGINS` — comma-separated allowed browser origins
- `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` — enable Adzuna search results
- `JOB_RSS_FEEDS` — JSON array of feeds your organization is authorized to consume, e.g. `[ {"name":"Company careers","url":"https://example.com/jobs.xml"} ]`

## API

- `GET /api/health` — app and model readiness
- `GET /api/jobs` — public job feed aggregator with source and query filters
- `POST /api/predict` — score structured job fields and save the result (guest or signed-in)
- `POST /api/analyze-url` — retrieve a public HTTPS job page, extract job text/JSON-LD and analyze it
- `POST /api/analyze` — compatibility endpoint for description-only model inference
- `POST /api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `GET /api/auth/session`
- `GET /api/history`, `GET /api/history/<id>` — signed-in user's analyses
- `GET /api/dashboard/stats` — signed-in user's prediction counts
- `GET /api/board-links` — external job-board search links

Register requires an email and a 10-character minimum password. Passwords are stored as Werkzeug password hashes. Session cookies are HTTP-only. Prediction history is private per account; guest checks can be analyzed but are not attached to a history account.

## Job sources and RSS

The feed adapter uses sources exposed for public consumption (Remote OK and Remotive), optional Adzuna API credentials, and explicitly configured RSS endpoints. The `/api/board-links` endpoint can provide Indeed, Naukri and LinkedIn search URLs to an integration. The app does not scrape behind job-board logins or access controls. Feed availability and fields vary by provider. Feed API endpoints remain available, but the curated listings panel is no longer shown in the interface.

## Poster and URL checks

Poster text is extracted in the browser with Tesseract.js, then shown in the editable job-post text box before the model runs. The image itself is not uploaded or stored. The first OCR use downloads/caches the English recognition data in the browser, so it needs internet access. URL checks accept public HTTPS pages only, reject non-public IP addresses and revalidate redirects; pages that require login or render content only in client-side JavaScript may not expose text for extraction. URL analysis uses the readable page text and supported `JobPosting` JSON-LD when present.

## Model and limits

The included dataset is a labeled, English-language job-posting dataset from the 2014-era EMSCAD study. It is useful for a project prototype but does not represent all current job markets, geographies, languages, or scam patterns. Its labels, age and class imbalance limit how well the model generalizes. `backend/models/training_metrics.json` records the stratified holdout results (including precision, recall, F1 and confusion matrix) for the run. Treat scores as screening estimates, not proof that an employer or post is fraudulent or safe. The short supporting-indicator list is a transparent checklist, not a feature-attribution explanation for the classifier.

Dataset mirror: [fake_job_postings.csv](https://huggingface.co/datasets/victor/real-or-fake-fake-jobposting-prediction/blob/main/fake_job_postings.csv), listed as CC0-1.0. Original study: [Employment Scam Aegean Dataset (EMSCAD)](https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-job-posting-prediction).

## Verify

```powershell
cd backend
python -m pytest tests -q
cd ..\frontend
npm run build
```
