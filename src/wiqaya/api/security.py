"""Guest sessions, roles, rate limiting, audit and genomic stripping (PROMPT.md §8.1, §13)."""

from __future__ import annotations

import os
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from wiqaya.common.paths import DATA
from wiqaya.governance.overlay import AuditLog, OverlayStore

ROLES = ("coordinator", "clinician", "planner", "family", "admin")
ROLE_INFO = {
    "coordinator": "Care coordinator: worklist, person and household detail, review decisions, outreach previews.",
    "clinician": "Clinician: everything a coordinator sees, plus genomic detail and sign-off of cascade tasks.",
    "planner": "Health-authority planner: aggregate, suppressed population metrics only.",
    "family": "Family member: the messages your household receives and your contact preferences.",
    "admin": "Administrator: rule library, provenance, model card, audit log, configuration (read-only).",
}
GENOMIC_ROLES = {"clinician", "admin"}
PERSON_ROLES = {"coordinator", "clinician", "admin"}
COOKIE = "wiqaya_session"
TTL = int(os.environ.get("SESSION_TTL_MINUTES", "120")) * 60


def _load_secret() -> str:
    """SESSION_SECRET from the environment; otherwise a local secret kept in data/ so restarts keep guest sessions."""
    env = os.environ.get("SESSION_SECRET")
    if env:
        return env
    path = DATA / ".session_secret"
    try:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        path.parent.mkdir(parents=True, exist_ok=True)
        value = secrets.token_hex(32)
        path.write_text(value, encoding="utf-8")
        return value
    except OSError:
        return secrets.token_hex(32)


_SECRET = _load_secret()
serializer = URLSafeTimedSerializer(_SECRET, salt="wiqaya-guest")
overlays = OverlayStore()
audit = AuditLog()


@dataclass(frozen=True)
class Session:
    sid: str
    role: str
    household_id: str = "hh-demo-001"  # family role: which demo household


def issue(role: str, sid: str | None = None, household_id: str = "hh-demo-001") -> str:
    if role not in ROLES:
        raise HTTPException(422, f"role must be one of {ROLES}")
    return serializer.dumps({"sid": sid or secrets.token_urlsafe(12), "role": role, "hh": household_id})


class RateLimiter:
    """Sliding-window limiter for guest session creation (per client IP)."""

    def __init__(self, limit: int = 30, window: float = 60.0) -> None:
        self.limit, self.window = limit, window
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                raise HTTPException(429, "Too many guest sessions from this address; try again shortly.")
            q.append(now)


guest_limiter = RateLimiter(int(os.environ.get("GUEST_RATE_LIMIT", "30")))


def current_session(request: Request) -> Session:
    token = request.cookies.get(COOKIE)
    auth = request.headers.get("authorization", "")
    if not token and auth.lower().startswith("bearer "):
        token = auth[7:]
    if not token:
        raise HTTPException(401, "No session. Use POST /api/v1/session/guest.")
    try:
        data = serializer.loads(token, max_age=TTL)
    except SignatureExpired as exc:
        raise HTTPException(401, "Session expired; start a new guest session.") from exc
    except BadSignature as exc:
        raise HTTPException(401, "Invalid session.") from exc
    return Session(str(data["sid"]), str(data["role"]), str(data.get("hh", "hh-demo-001")))


def require(*roles: str) -> Any:
    def dep(s: Session = Depends(current_session)) -> Session:  # noqa: B008
        if s.role not in roles:
            raise HTTPException(403, f"Role '{s.role}' cannot access this resource.")
        return s

    return dep


def strip_genomic(obj: Any, role: str) -> Any:
    """Remove genomic and index-identifying fields for roles other than clinician/admin."""
    if role in GENOMIC_ROLES:
        return obj
    hidden = {"genomic", "index_person_ids", "index_reasons", "genomic_flag", "variant", "gene"}
    if isinstance(obj, dict):
        return {
            k: ("restricted (clinician/admin only)" if k in hidden else strip_genomic(v, role)) for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [strip_genomic(v, role) for v in obj]
    return obj
