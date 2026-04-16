"""
middleware_login.py
-------------------
JWT authentication middleware for all /api/* routes.

Runs as a Flask before_request hook. For every request to /api/*
(except /api/login which is the public auth endpoint):

  1. Reads the Authorization: Bearer <token> header
  2. Decodes and validates the JWT
  3. Stores the decoded UserContext in flask.g.user_ctx

Any route under /api/* can then access the authenticated user via:

    from flask import g
    ctx = g.user_ctx          # UserContext(user_id, username, role)

Or use the @require_auth decorator from user_context.py which does
the same thing but injects user_ctx as a function argument.
"""

import jwt
from flask import request, jsonify, g, current_app
from user_context import UserContext

# Routes that do NOT require a token
PUBLIC_ROUTES = {
    "/api/login",
}


def _decode_bearer() -> UserContext:
    """
    Extract and decode the Bearer token from the Authorization header.
    Raises ValueError with a human-readable message on any failure.
    """
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        raise ValueError(
            "Missing or malformed Authorization header. "
            "Expected: 'Authorization: Bearer <token>'"
        )

    token_str = auth_header[len("Bearer "):]

    try:
        payload = jwt.decode(
            token_str,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired. Please login again.")
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}")

    return UserContext(
        user_id  = payload.get("user_id") or int(payload.get("sub", 0)),
        username = payload.get("username", ""),
        role     = payload.get("role", "user"),
    )


def jwt_middleware():
    """
    before_request handler — registered in app.py via:
        app.before_request(jwt_middleware)

    Intercepts every /api/* request that is not in PUBLIC_ROUTES.
    On success  → stores UserContext in g.user_ctx and continues.
    On failure  → returns a 401 JSON response immediately.
    OPTIONS requests are always passed through (CORS preflight).
    """
    path = request.path

    # Only guard /api/* routes
    if not path.startswith("/api/"):
        return None

    # Always allow CORS preflight
    if request.method == "OPTIONS":
        return None

    # Public routes skip auth
    if path in PUBLIC_ROUTES:
        return None

    try:
        g.user_ctx = _decode_bearer()
    except ValueError as exc:
        return jsonify({
            "error":   str(exc),
            "hint":    "Obtain a token from POST /api/login and send it as "
                       "'Authorization: Bearer <token>'",
        }), 401

    return None   # continue to the actual view
