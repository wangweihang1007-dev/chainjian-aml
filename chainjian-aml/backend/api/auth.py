"""PostgreSQL-backed authentication for the AML workspace."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from core.database import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from core.warehouse import DEFAULT_DATABASE


router = APIRouter(prefix="/auth", tags=["auth"])
SESSION_HOURS = 8
DEFAULT_PASSWORD_HASH = "pbkdf2_sha256$240000$944d0994752b66be9490ae74c163b42a$9f48888c285b3a4225072c1b941d99d0141e304c6b544114f96b3af876c5d764"


class LoginRequest(BaseModel):
    username: str
    password: str


AUTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_user (
    username TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_session (
    token TEXT PRIMARY KEY,
    username TEXT NOT NULL REFERENCES app_user(username),
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DEFAULT_DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(AUTH_SCHEMA)
    connection.execute(
        "INSERT OR IGNORE INTO app_user (username, display_name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
        ("compliance.reviewer", "合规审核员", DEFAULT_PASSWORD_HASH, "reviewer", _now().isoformat(timespec="seconds")),
    )
    connection.commit()
    return connection


def _verify_password(password: str, encoded: str) -> bool:
    algorithm, rounds, salt, expected = encoded.split("$", 3)
    if algorithm != "pbkdf2_sha256":
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
    return hmac.compare_digest(actual, expected)


def current_user(authorization: str | None) -> sqlite3.Row | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    with _connect() as connection:
        row = connection.execute(
            "SELECT u.* FROM auth_session s JOIN app_user u ON u.username = s.username WHERE s.token = ? AND s.expires_at > ? AND u.active = 1",
            (token, _now().isoformat(timespec="seconds")),
        ).fetchone()
    return row


@router.post("/login")
def login(request: LoginRequest) -> dict:
    username = request.username.strip()
    with _connect() as connection:
        user = connection.execute("SELECT * FROM app_user WHERE username = ? AND active = 1", (username,)).fetchone()
        if not user or not _verify_password(request.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        token = secrets.token_urlsafe(32)
        now = _now()
        connection.execute(
            "INSERT INTO auth_session (token, username, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token, username, (now + timedelta(hours=SESSION_HOURS)).isoformat(timespec="seconds"), now.isoformat(timespec="seconds")),
        )
        connection.commit()
    return {"access_token": token, "token_type": "bearer", "expires_at": (now + timedelta(hours=SESSION_HOURS)).isoformat(timespec="seconds"), "user": {"username": username, "display_name": user["display_name"], "role": user["role"]}}


@router.get("/me")
def me(authorization: str | None = Header(default=None)) -> dict:
    user = current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效")
    return {"username": user["username"], "display_name": user["display_name"], "role": user["role"]}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    if authorization and authorization.lower().startswith("bearer "):
        with _connect() as connection:
            connection.execute("DELETE FROM auth_session WHERE token = ?", (authorization[7:].strip(),))
            connection.commit()
    return {"ok": True}
