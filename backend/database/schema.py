from database.db import get_db

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        job_title TEXT NOT NULL DEFAULT '',
        company_name TEXT NOT NULL DEFAULT '',
        prediction TEXT NOT NULL CHECK (prediction IN ('REAL','FAKE')),
        confidence REAL NOT NULL,
        fake_probability REAL NOT NULL,
        risk_level TEXT NOT NULL CHECK (risk_level IN ('LOW','MEDIUM','HIGH')),
        input_json TEXT NOT NULL,
        explanation_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS ix_predictions_user_created ON predictions(user_id, created_at DESC);
    """)
    db.commit()
