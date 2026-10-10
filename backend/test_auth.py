import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.auth import (
    AuthSession,
    AuthenticatedSession,
    User,
    hash_password,
    normalize_account,
    require_session,
    verify_password,
)


class PasswordHashTests(unittest.TestCase):
    def test_password_hash_is_salted_versioned_and_verifiable(self) -> None:
        first = hash_password("correct horse battery staple")
        second = hash_password("correct horse battery staple")

        self.assertTrue(first.startswith("scrypt$v=1$"))
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password("correct horse battery staple", first))
        self.assertFalse(verify_password("wrong password", first))
        self.assertFalse(verify_password("correct horse battery staple", "not-a-valid-hash"))

    def test_account_normalization_is_stable(self) -> None:
        self.assertEqual(normalize_account("  USER@Example.COM  "), "user@example.com")


class SessionDependencyTests(unittest.TestCase):
    def test_valid_bearer_token_returns_immutable_identity(self) -> None:
        user_id = uuid4()
        session_id = uuid4()
        user = SimpleNamespace(
            id=user_id,
            account="user@example.test",
            display_name="Test User",
            role_id="planner",
            is_active=True,
        )
        auth_session = SimpleNamespace(
            id=session_id,
            revoked_at=None,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db = MagicMock()
        db.execute.return_value.one_or_none.return_value = (auth_session, user)

        identity = require_session(HTTPAuthorizationCredentials(scheme="Bearer", credentials="opaque-token"), db)

        self.assertEqual(
            identity,
            AuthenticatedSession(user_id, "user@example.test", "Test User", "planner", session_id),
        )
        with self.assertRaises((AttributeError, TypeError)):
            identity.account = "changed"  # type: ignore[misc]

    def test_missing_expired_and_revoked_sessions_are_rejected(self) -> None:
        db = MagicMock()
        with self.assertRaises(HTTPException) as missing:
            require_session(None, db)
        self.assertEqual(missing.exception.status_code, 401)

        user = SimpleNamespace(is_active=True)
        for revoked_at, expires_at in (
            (datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=1)),
            (None, datetime.now(timezone.utc) - timedelta(seconds=1)),
        ):
            db.execute.return_value.one_or_none.return_value = (
                SimpleNamespace(revoked_at=revoked_at, expires_at=expires_at),
                user,
            )
            with self.assertRaises(HTTPException) as rejected:
                require_session(HTTPAuthorizationCredentials(scheme="Bearer", credentials="opaque-token"), db)
            self.assertEqual(rejected.exception.status_code, 401)


class LoginSecurityTests(unittest.TestCase):
    def test_unknown_account_still_runs_password_verification(self) -> None:
        from backend.auth import LoginRequest, login

        db = MagicMock()
        db.scalar.return_value = None
        with patch("backend.auth.verify_password", wraps=verify_password) as verify:
            with self.assertRaises(HTTPException) as rejected:
                login(LoginRequest(account="missing", password="some password"), db)
        self.assertEqual(rejected.exception.status_code, 401)
        self.assertEqual(rejected.exception.detail, "Invalid account or password")
        verify.assert_called_once()

    def test_successful_login_stores_only_token_hash(self) -> None:
        from backend.auth import LoginRequest, login

        user = User(
            id=uuid4(),
            account="planner@example.test",
            display_name="Planner",
            role_id="planner",
            password_hash=hash_password("a sufficiently long password"),
            is_active=True,
        )
        db = MagicMock()
        db.scalar.return_value = user

        response = login(LoginRequest(account="planner@example.test", password="a sufficiently long password"), db)

        stored_session = db.add.call_args.args[0]
        self.assertIsInstance(stored_session, AuthSession)
        self.assertNotEqual(stored_session.token_hash, response.session_token)
        self.assertEqual(len(stored_session.token_hash), 64)
        db.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
