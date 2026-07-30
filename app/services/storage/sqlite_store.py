import asyncio
import json
import os
import sqlite3
from pathlib import Path
from typing import Any


def _db_path() -> Path:
    configured = os.getenv("SQLITE_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "sandy_core.sqlite3"


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db_sync() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY,
                settings_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS twitch_tokens (
                user_id TEXT NOT NULL,
                bot INTEGER NOT NULL DEFAULT 0,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, bot)
            );
            """
        )
        conn.commit()


async def initialize_db() -> None:
    await asyncio.to_thread(initialize_db_sync)


def upsert_user_settings_sync(user_id: str, settings: dict[str, Any]) -> None:
    initialize_db_sync()
    payload = json.dumps(settings)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO user_settings (user_id, settings_json, created_at, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                settings_json = excluded.settings_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, payload),
        )
        conn.commit()


async def upsert_user_settings(user_id: str, settings: dict[str, Any]) -> None:
    await asyncio.to_thread(upsert_user_settings_sync, user_id, settings)


def get_user_settings_sync(user_id: str) -> dict[str, Any] | None:
    initialize_db_sync()
    with _connect() as conn:
        row = conn.execute(
            "SELECT settings_json FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["settings_json"])


async def get_user_settings(user_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(get_user_settings_sync, user_id)


def save_twitch_tokens_sync(
    user_id: str, token: str, refresh_token: str, bot: bool = False
) -> None:
    initialize_db_sync()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO twitch_tokens (
                user_id, bot, access_token, refresh_token, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, bot) DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, int(bot), token, refresh_token),
        )
        conn.commit()


async def save_twitch_tokens(
    user_id: str, token: str, refresh_token: str, bot: bool = False
) -> None:
    await asyncio.to_thread(save_twitch_tokens_sync, user_id, token, refresh_token, bot)


def get_twitch_tokens_sync(user_id: str, bot: bool = False) -> dict[str, str] | None:
    initialize_db_sync()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT access_token, refresh_token
            FROM twitch_tokens
            WHERE user_id = ? AND bot = ?
            """,
            (user_id, int(bot)),
        ).fetchone()
        if row is None:
            return None
        return {
            "token": row["access_token"],
            "refresh_token": row["refresh_token"],
        }


async def get_twitch_tokens(user_id: str, bot: bool = False) -> dict[str, str] | None:
    return await asyncio.to_thread(get_twitch_tokens_sync, user_id, bot)

