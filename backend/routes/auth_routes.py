import sqlite3

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db

auth = Blueprint("auth", __name__, url_prefix="/api/auth")


def current_user():
    if not session.get("user_id"):
        return None
    return {"id": session["user_id"], "email": session["email"]}


@auth.get("/session")
def session_status():
    return jsonify({"user": current_user()})


@auth.post("/register")
def register():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "")
    password = body.get("password", "")
    if not isinstance(email, str) or "@" not in email or len(email) > 254:
        return jsonify({"error": "Enter a valid email address."}), 400
    if not isinstance(password, str) or len(password) < 10:
        return jsonify({"error": "Use a password with at least 10 characters."}), 400
    try:
        db = get_db()
        cursor = db.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email.strip().lower(), generate_password_hash(password)))
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this email already exists."}), 409
    session.clear()
    session["user_id"] = cursor.lastrowid
    session["email"] = email.strip().lower()
    return jsonify({"user": current_user()}), 201


@auth.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "")
    password = body.get("password", "")
    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({"error": "Enter your email and password."}), 400
    user = get_db().execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Email or password is incorrect."}), 401
    session.clear()
    session["user_id"] = user["id"]
    session["email"] = user["email"]
    return jsonify({"user": current_user()})


@auth.post("/logout")
def logout():
    session.clear()
    return jsonify({"success": True})
