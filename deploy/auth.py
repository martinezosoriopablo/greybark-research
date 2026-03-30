"""
auth.py — JWT Authentication for FastAPI Portal
================================================
Cookie-based JWT auth with bcrypt password hashing.
Validates against greybark_platform.py client database.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt as _bcrypt
from fastapi import Request, HTTPException, status
from jose import JWTError, jwt

# ── Config ────────────────────────────────────────────────

SECRET_KEY = os.environ.get("JWT_SECRET")
if not SECRET_KEY:
    import warnings
    warnings.warn("JWT_SECRET env var not set — using insecure default. Set it in production!", stacklevel=2)
    SECRET_KEY = "change-me-in-production-use-openssl-rand-hex-32"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.environ.get("TOKEN_EXPIRE_MINUTES", "480"))  # 8 hours
COOKIE_NAME = "gb_session"


# ── Password helpers ──────────────────────────────────────

def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT helpers ───────────────────────────────────────────

def create_access_token(client_id: str, extra: dict = None) -> str:
    payload = {
        "sub": client_id,
        "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
        "iat": datetime.utcnow(),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    """Decode JWT and return client_id, or None if invalid/expired."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


# ── FastAPI dependency ────────────────────────────────────

def get_current_client(request: Request) -> str:
    """
    FastAPI dependency: extract client_id from JWT cookie.
    Raises 401 → redirects to /login if missing/invalid.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"},
        )

    client_id = decode_token(token)
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"},
        )

    return client_id
