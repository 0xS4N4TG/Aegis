"""
Database models and store — SQLite persistence via aiosqlite.
"""

from __future__ import annotations

import json
import aiosqlite
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings


# ── SQL Schema ──────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attacks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    technique   TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    prompt      TEXT    NOT NULL,
    response    TEXT    NOT NULL,
    model       TEXT    NOT NULL DEFAULT '',
    refused     INTEGER NOT NULL DEFAULT 0,
    api_blocked INTEGER NOT NULL DEFAULT 0,
    policy_bypass  INTEGER NOT NULL DEFAULT 0,
    info_leaked    INTEGER NOT NULL DEFAULT 0,
    jailbreak_score   REAL NOT NULL DEFAULT 0.0,
    harmful_score     REAL NOT NULL DEFAULT 0.0,
    duration_ms       REAL NOT NULL DEFAULT 0.0,
    notes       TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    category    TEXT    NOT NULL,
    severity    TEXT    NOT NULL DEFAULT 'medium',
    prompt_tmpl TEXT    NOT NULL,
    tags        TEXT    NOT NULL DEFAULT '[]',
    description TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL
);


"""


class ResultStore:
    """Async SQLite wrapper for attack results and templates."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or settings.db_path

    async def _get_db(self) -> aiosqlite.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(str(self._db_path))
        db.row_factory = aiosqlite.Row
        return db

    async def init_db(self) -> None:
        """Create tables if they don't exist."""
        db = await self._get_db()
        try:
            await db.executescript(_SCHEMA)
            await db.commit()
        finally:
            await db.close()

    # ── Attack results ──────────────────────────────────────────

    async def save_attack(self, result: dict[str, Any]) -> int:
        """Insert an attack result; returns the row id."""
        db = await self._get_db()
        try:
            cursor = await db.execute(
                """INSERT INTO attacks
                   (timestamp, technique, category, prompt, response, model,
                    refused, api_blocked, policy_bypass, info_leaked,
                    jailbreak_score, harmful_score, duration_ms, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    result.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    result["technique"],
                    result["category"],
                    result["prompt"],
                    result["response"],
                    result.get("model", ""),
                    int(result.get("refused", False)),
                    int(result.get("api_blocked", False)),
                    int(result.get("policy_bypass", False)),
                    int(result.get("info_leaked", False)),
                    result.get("jailbreak_score", 0.0),
                    result.get("harmful_score", 0.0),
                    result.get("duration_ms", 0.0),
                    result.get("notes", ""),
                ),
            )
            await db.commit()
            return cursor.lastrowid  # type: ignore[return-value]
        finally:
            await db.close()

    async def get_attacks(
        self,
        *,
        limit: int = 100,
        category: str | None = None,
        success_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve attack results with optional filters."""
        db = await self._get_db()
        try:
            query = "SELECT * FROM attacks WHERE 1=1"
            params: list[Any] = []

            if category:
                query += " AND category = ?"
                params.append(category)
            if success_only:
                query += " AND refused = 0 AND jailbreak_score >= 50"

            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            await db.close()

    async def get_stats(self) -> dict[str, Any]:
        """Aggregate statistics for the dashboard."""
        db = await self._get_db()
        try:
            total = await (await db.execute("SELECT COUNT(*) FROM attacks")).fetchone()
            success = await (
                await db.execute(
                    "SELECT COUNT(*) FROM attacks WHERE refused=0 AND jailbreak_score>=50"
                )
            ).fetchone()
            avg_score = await (
                await db.execute("SELECT AVG(jailbreak_score) FROM attacks")
            ).fetchone()

            # Per-category breakdown
            cat_cursor = await db.execute(
                """SELECT category,
                          COUNT(*) as total,
                          SUM(CASE WHEN refused=0 AND jailbreak_score>=50 THEN 1 ELSE 0 END) as successes
                   FROM attacks GROUP BY category"""
            )
            categories = [dict(r) for r in await cat_cursor.fetchall()]

            return {
                "total_attacks": total[0] if total else 0,
                "successful_jailbreaks": success[0] if success else 0,
                "avg_jailbreak_score": round(avg_score[0] or 0, 1) if avg_score else 0,
                "categories": categories,
            }
        finally:
            await db.close()

    # ── Templates ───────────────────────────────────────────────

    async def save_template(self, tmpl: dict[str, Any]) -> int:
        """Upsert a jailbreak template."""
        db = await self._get_db()
        try:
            cursor = await db.execute(
                """INSERT OR REPLACE INTO templates
                   (name, category, severity, prompt_tmpl, tags, description, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    tmpl["name"],
                    tmpl["category"],
                    tmpl.get("severity", "medium"),
                    tmpl["prompt"],
                    json.dumps(tmpl.get("tags", [])),
                    tmpl.get("description", ""),
                    tmpl.get("created_at", datetime.now(timezone.utc).isoformat()),
                ),
            )
            await db.commit()
            return cursor.lastrowid  # type: ignore[return-value]
        finally:
            await db.close()

    async def get_templates(
        self, *, category: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve jailbreak templates."""
        db = await self._get_db()
        try:
            if category:
                cursor = await db.execute(
                    "SELECT * FROM templates WHERE category=? ORDER BY name",
                    (category,),
                )
            else:
                cursor = await db.execute("SELECT * FROM templates ORDER BY name")
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["tags"] = json.loads(d.get("tags", "[]"))
                result.append(d)
            return result
        finally:
            await db.close()


