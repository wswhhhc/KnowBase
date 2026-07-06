from __future__ import annotations

import shutil
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.api.auth_tokens import hash_password
from src.config.settings import ROOT_DIR, settings
from src.persistence import auth_store, workspace_store
from src.persistence.database import init_db
from src.persistence.schema import metadata
from src.persistence.sqlalchemy_database import create_engine_for_url, get_engine, get_session_factory


RUNTIME_DIR = ROOT_DIR / "runtime" / "e2e"
USERS = [
    ("admin", "admin-pass", "admin"),
    ("editor", "editor-pass", "editor"),
    ("viewer", "viewer-pass", "viewer"),
]


def reset_runtime() -> None:
    if RUNTIME_DIR.exists():
        shutil.rmtree(RUNTIME_DIR)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def ensure_user(username: str, password: str, role: str) -> dict:
    user = auth_store.get_user_by_username(username)
    password_hash = hash_password(password)
    if user is None:
        return auth_store.create_user(
            username=username,
            password_hash=password_hash,
            role=role,
            is_active=True,
        )
    auth_store.update_user(
        user["id"],
        password_hash=password_hash,
        role=role,
        is_active=True,
    )
    return auth_store.get_user_by_id(user["id"]) or user


def main() -> None:
    reset_runtime()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    init_db()
    metadata.create_all(create_engine_for_url(settings.storage.database_url))

    seeded_users = {
        username: ensure_user(username, password, role)
        for username, password, role in USERS
    }
    default_workspace = workspace_store.list_workspaces()[0]
    auth_store.replace_workspace_members(
        workspace_id=default_workspace["id"],
        members=[
            {"user_id": seeded_users["editor"]["id"], "role": "editor"},
            {"user_id": seeded_users["viewer"]["id"], "role": "viewer"},
        ],
    )
    print("Prepared KnowBase E2E environment")


if __name__ == "__main__":
    main()
