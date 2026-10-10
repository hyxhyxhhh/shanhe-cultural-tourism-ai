from __future__ import annotations

import base64
import hashlib
import os
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Iterator
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import Boolean, DateTime, ForeignKey, String, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.db import Base, SessionLocal


_PASSWORD_SCHEME = "scrypt"
_PASSWORD_VERSION = "1"
_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_KEY_LENGTH = 32
_SCRYPT_MAX_MEMORY = 64 * 1024 * 1024
_DEFAULT_SESSION_TTL_HOURS = 12
_MAX_BEARER_TOKEN_LENGTH = 512
USER_ROLE_IDS = (
    "government",
    "group-executive",
    "scenic-operator",
    "creative-design",
    "project-team",
    "licensed-institution",
    "expert-advisor",
    "management",
    "platform-admin",
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    account: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role_id: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: _utc_now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: _utc_now(), onupdate=lambda: _utc_now()
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: _utc_now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    user_id: UUID
    account: str
    display_name: str
    role_id: str
    session_id: UUID


# Activity routers use the identity-oriented name; keep the session-oriented
# name as a compatibility alias for callers that need the revocable session id.
AuthenticatedUser = AuthenticatedSession


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account: str = Field(min_length=1, max_length=200)
    password: SecretStr = Field(min_length=1, max_length=1024)


class UserDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: UUID = Field(alias="userId")
    account: str
    display_name: str = Field(alias="displayName")
    role_id: str = Field(alias="roleId")


class LoginResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_token: str = Field(alias="sessionToken")
    token_type: str = Field(default="bearer", alias="tokenType")
    expires_at: datetime = Field(alias="expiresAt")
    user: UserDTO


router = APIRouter(prefix="/api/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_account(account: str) -> str:
    normalized = unicodedata.normalize("NFKC", account).strip().casefold()
    if not normalized or len(normalized) > 200:
        raise ValueError("account must contain 1 to 200 characters")
    return normalized


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password is required")
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_KEY_LENGTH,
        maxmem=_SCRYPT_MAX_MEMORY,
    )
    return "$".join(
        (
            _PASSWORD_SCHEME,
            f"v={_PASSWORD_VERSION}",
            f"n={_SCRYPT_N}",
            f"r={_SCRYPT_R}",
            f"p={_SCRYPT_P}",
            _encode(salt),
            _encode(derived),
        )
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        scheme, version, n_value, r_value, p_value, salt_value, digest_value = encoded_hash.split("$")
        if scheme != _PASSWORD_SCHEME or version != f"v={_PASSWORD_VERSION}":
            return False
        n = int(n_value.removeprefix("n="))
        r = int(r_value.removeprefix("r="))
        p = int(p_value.removeprefix("p="))
        if (n, r, p) != (_SCRYPT_N, _SCRYPT_R, _SCRYPT_P):
            return False
        salt = _decode(salt_value)
        expected = _decode(digest_value)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
            maxmem=_SCRYPT_MAX_MEMORY,
        )
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(actual, expected)


_DUMMY_PASSWORD_HASH = hash_password("dummy-password-used-only-for-login-timing")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _session_ttl() -> timedelta:
    raw_value = os.environ.get("AUTH_SESSION_TTL_HOURS", str(_DEFAULT_SESSION_TTL_HOURS))
    try:
        hours = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("AUTH_SESSION_TTL_HOURS must be an integer") from exc
    if hours < 1 or hours > 24 * 30:
        raise RuntimeError("AUTH_SESSION_TTL_HOURS must be between 1 and 720")
    return timedelta(hours=hours)


def get_db_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db_session)]
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def _authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_session(credentials: BearerCredentials, db: DbSession) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise _authentication_error()
    token = credentials.credentials
    if not token or len(token) > _MAX_BEARER_TOKEN_LENGTH:
        raise _authentication_error()
    try:
        token_hash = _token_hash(token)
    except UnicodeEncodeError:
        raise _authentication_error() from None

    row = db.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.token_hash == token_hash)
    ).one_or_none()
    if row is None:
        raise _authentication_error()
    auth_session, user = row
    if auth_session.revoked_at is not None or auth_session.expires_at <= _utc_now() or not user.is_active:
        raise _authentication_error()
    return AuthenticatedUser(
        user_id=user.id,
        account=user.account,
        display_name=user.display_name,
        role_id=user.role_id,
        session_id=auth_session.id,
    )


CurrentSession = Annotated[AuthenticatedUser, Depends(require_session)]


def _user_dto(user: User | AuthenticatedUser) -> UserDTO:
    user_id = user.id if isinstance(user, User) else user.user_id
    return UserDTO(userId=user_id, account=user.account, displayName=user.display_name, roleId=user.role_id)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: DbSession) -> LoginResponse:
    try:
        account = normalize_account(payload.account)
    except ValueError:
        account = ""
    user = db.scalar(select(User).where(User.account == account)) if account else None

    # Always run scrypt, including for an unknown account, so the response does not
    # reveal account existence through the normal fast/slow timing difference.
    encoded_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_valid = verify_password(payload.password.get_secret_value(), encoded_hash)
    if user is None or not password_valid or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid account or password")

    token = secrets.token_urlsafe(48)
    expires_at = _utc_now() + _session_ttl()
    auth_session = AuthSession(user_id=user.id, token_hash=_token_hash(token), expires_at=expires_at)
    db.add(auth_session)
    db.commit()
    return LoginResponse(sessionToken=token, expiresAt=expires_at, user=_user_dto(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current: CurrentSession, db: DbSession) -> Response:
    auth_session = db.get(AuthSession, current.session_id)
    if auth_session is not None and auth_session.revoked_at is None:
        auth_session.revoked_at = _utc_now()
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserDTO)
def me(current: CurrentSession) -> UserDTO:
    return _user_dto(current)
