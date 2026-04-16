import jwt
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import check_password_hash

from extensions import db
from login_model import Token
from user_context import require_auth, UserContext

login_bp = Blueprint("login_bp", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# POST /api/login
# Body (JSON): { "username": "...", "password": "..." }
# ---------------------------------------------------------------------------
@login_bp.route("/login", methods=["POST", "OPTIONS"])
def api_login():
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return jsonify({}), 200

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    # Import User from models (not app) to avoid circular import / re-execution
    from models import User

    user = User.query.filter_by(username=username).first()

    if not user or not check_password_hash(user.password, password):
        return jsonify({"error": "Invalid username or password"}), 401

    # Build JWT payload
    now = datetime.now(timezone.utc)
    payload = {
        "sub":      str(user.id),       # PyJWT requires sub to be a string
        "user_id":  user.id,            # keep int separately for easy access
        "username": user.username,
        "role":     user.role,
        "iat":      now,
        "exp":      now + timedelta(hours=24),
    }

    token_str = jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    # Persist token to the tokens table (revoked_is defaults to 0)
    record = Token(
        token      = token_str,
        user_id    = user.id,
        revoked_is = 0,
        created_at = now.date(),
    )
    db.session.add(record)
    db.session.commit()

    return jsonify({
        "message":    "Login successful",
        "token":      token_str,
        "token_type": "Bearer",
        "expires_in": 86400,   # seconds (24 h)
        "user": {
            "id":       user.id,
            "username": user.username,
            "role":     user.role,
        },
    }), 200


# ---------------------------------------------------------------------------
# GET /api/me  — returns the user identity encoded in the JWT
# ---------------------------------------------------------------------------
@login_bp.route("/me", methods=["GET"])
@require_auth
def api_me(user_ctx: UserContext):
    return jsonify({
        "user_id":  user_ctx.user_id,
        "username": user_ctx.username,
        "role":     user_ctx.role,
    }), 200
