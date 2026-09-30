import sqlite3
from flask import current_app, g
from config import DATABASE_PATH

def get_db():
    if "db" not in g:
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(DATABASE_PATH, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db

def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()

def init_app(app):
    app.teardown_appcontext(close_db)
