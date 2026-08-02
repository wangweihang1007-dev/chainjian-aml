"""HTTP client used by Streamlit; the frontend never opens the warehouse directly."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass


BACKEND_API_URL = os.getenv("AML_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


class BackendUnavailable(RuntimeError):
    pass


def request_json(path: str, method: str = "GET", payload: dict | None = None) -> dict | list:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(f"{BACKEND_API_URL}{path}", data=body, method=method, headers={"Accept": "application/json", "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise BackendUnavailable(f"Backend returned {error.code}: {detail}") from error
    except URLError as error:
        raise BackendUnavailable(f"Backend unavailable at {BACKEND_API_URL}: {error.reason}") from error


def path_id(value: str) -> str:
    return quote(value, safe="")
