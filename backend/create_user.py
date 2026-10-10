from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.auth import USER_ROLE_IDS, User, hash_password, normalize_account
from backend.db import SessionLocal


def _non_empty(value: str, label: str, maximum: int) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum:
        raise ValueError(f"{label} must contain 1 to {maximum} characters")
    return cleaned


def create_user(*, account: str, display_name: str, role_id: str, password: str) -> User:
    normalized_account = normalize_account(account)
    clean_display_name = _non_empty(display_name, "display name", 200)
    clean_role_id = _non_empty(role_id, "role id", 64)
    if clean_role_id not in USER_ROLE_IDS:
        raise ValueError("role id is not supported")
    if len(password) < 16:
        raise ValueError("password must contain at least 16 characters")

    with SessionLocal.begin() as session:
        if session.scalar(select(User.id).where(User.account == normalized_account)) is not None:
            raise ValueError("account already exists")
        user = User(
            account=normalized_account,
            display_name=clean_display_name,
            role_id=clean_role_id,
            password_hash=hash_password(password),
        )
        session.add(user)
        session.flush()
    return user


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local Shanhe application user.")
    parser.add_argument("--account", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role-id", choices=USER_ROLE_IDS, default="platform-admin")
    args = parser.parse_args()

    password = getpass.getpass("Password (hidden, at least 16 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2
    try:
        user = create_user(
            account=args.account,
            display_name=args.display_name,
            role_id=args.role_id,
            password=password,
        )
    except (ValueError, IntegrityError) as exc:
        print(f"User was not created: {exc}", file=sys.stderr)
        return 1
    finally:
        password = ""
        confirmation = ""

    print(f"Created user {user.account!r} with role {user.role_id!r}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
