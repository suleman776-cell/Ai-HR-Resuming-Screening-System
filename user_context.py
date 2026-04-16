"""
UserContext
-----------
Decodes the Bearer JWT from the current request and exposes the
encoded user identity (user_id, username, role) as a typed object.

Usage in any route / blueprint:
    from user_context import get_user_context, UserContext

    ctx = get_user_context()   # returns UserContext or raises 401 response
    print(ctx.user_id, ctx.username, ctx.role)

Decorator usage:
    from user_context import require_auth

    @app.route("/api/protected")
    @require_auth
    def protected():
        ctx = get_user_context()
        return jsonify({"hello": ctx.username})
"""

from __future__ import annotations

import jwt
from dataclasses import dataclass
from functools import wraps
from flask import request, jsonify, current_app


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------
@dataclass
class UserContext:
    user_id:  int
    username: str
    role:     str

    def is_admin(self) -> bool:
        return self.role == "admin"


# ---------------------------------------------------------------------------
# Internal: extract & decode the token from the Authorization header
# ---------------------------------------------------------------------------
def _decode_token() -> dict:
    """
    Reads the Authorization header, strips 'Bearer ', and decodes the JWT.
    Raises ValueError with a human-readable message on any failure.
    """
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        raise ValueError("Missing or malformed Authorization header. "
                         "Expected: 'Bearer <token>'")

    token_str = auth_header[len("Bearer "):]

    try:
        payload = jwt.decode(
            token_str,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}")

    return payload


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_user_context() -> UserContext:
    """
    Decode the JWT and return a UserContext.
    Raises a Flask JSON 401 response tuple on failure — callers should
    return it directly:

        ctx_or_err = get_user_context()
        if isinstance(ctx_or_err, tuple):   # error response
            return ctx_or_err
    """
    try:
        payload = _decode_token()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 401   # type: ignore[return-value]

    return UserContext(
        user_id  = payload.get("user_id") or int(payload.get("sub", 0)),
        username = payload.get("username"),
        role     = payload.get("role", "user"),
    )


def require_auth(f):
    """
    Decorator that enforces a valid JWT on a route.
    Injects a `user_ctx: UserContext` keyword argument into the view function.

    Example:
        @app.route("/api/me")
        @require_auth
        def me(user_ctx: UserContext):
            return jsonify({"username": user_ctx.username, "id": user_ctx.user_id})
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            payload = _decode_token()
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 401

        ctx = UserContext(
            user_id  = payload.get("user_id") or int(payload.get("sub", 0)),
            username = payload.get("username"),
            role     = payload.get("role", "user"),
        )
        return f(*args, user_ctx=ctx, **kwargs)

    return decorated
