# Clearhire frontend

React + Vite interface for checking pasted job text, OCR text from a poster image, or a public job-post URL. Poster OCR runs in the browser; the image is not sent to Flask. The interface also includes sign-in, prediction history, and dashboard views.

```powershell
npm install
npm run dev
```

Run Flask from the `backend/` folder in a second terminal. Vite proxies `/api` requests to `http://127.0.0.1:5000`.

See the repository [README](../README.md) for model training, API routes, environment variables, URL-fetching limits, and setup instructions.
