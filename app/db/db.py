"""
SQLite database manager.
Uses WAL mode for safe concurrent reads/writes across threads.
Each thread gets its own connection via threading.local().
"""

import logging
import os
import sqlite3
import threading

from db.models import content_item_from_row

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS content_items (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    topic                 TEXT    NOT NULL,
    status                TEXT    NOT NULL DEFAULT 'pending_approval'
                          CHECK (status IN (
                              'pending_approval',
                              'approved',
                              'rejected',
                              'generating_content',
                              'generating_image',
                              'preview_pending',
                              'scheduled',
                              'publishing',
                              'published',
                              'failed'
                          )),
    generated_title       TEXT,
    generated_description TEXT,
    generated_hashtags    TEXT,
    image_local_path      TEXT,
    image_prompt          TEXT,
    subject               TEXT,
    headline              TEXT,
    fact_text             TEXT,
    highlight_1           TEXT,
    highlight_2           TEXT,
    category              TEXT,
    ai33pro_task_id       TEXT,
    fb_post_id            TEXT,
    telegram_msg_id       INTEGER,
    telegram_chat_id      INTEGER,
    error_message         TEXT,
    created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    updated_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_content_items_status
    ON content_items(status);
CREATE INDEX IF NOT EXISTS idx_content_items_created
    ON content_items(created_at);

CREATE TABLE IF NOT EXISTS usage_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    provider    TEXT    NOT NULL CHECK (provider IN ('gemini', 'ai33pro', 'telegram', 'facebook')),
    endpoint    TEXT    NOT NULL,
    credit_cost REAL    DEFAULT 0,
    success     INTEGER NOT NULL DEFAULT 1,
    error_msg   TEXT,
    timestamp   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_usage_log_provider
    ON usage_log(provider);
CREATE INDEX IF NOT EXISTS idx_usage_log_timestamp
    ON usage_log(timestamp);

CREATE TABLE IF NOT EXISTS topic_source_rows (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file     TEXT    NOT NULL,
    row_index       INTEGER NOT NULL,
    topic           TEXT    NOT NULL,
    consumed        INTEGER NOT NULL DEFAULT 0,
    content_item_id INTEGER,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    FOREIGN KEY (content_item_id) REFERENCES content_items(id)
);

CREATE INDEX IF NOT EXISTS idx_topic_source_rows_file
    ON topic_source_rows(source_file, consumed);

CREATE TABLE IF NOT EXISTS scheduled_posts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    content_item_id   INTEGER NOT NULL,
    target_region     TEXT    NOT NULL,
    scheduled_time_utc TEXT   NOT NULL,
    status            TEXT    NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'posted', 'failed')),
    created_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    FOREIGN KEY (content_item_id) REFERENCES content_items(id)
);

CREATE INDEX IF NOT EXISTS idx_scheduled_posts_status
    ON scheduled_posts(status, scheduled_time_utc);
"""


class Database:
    """Thread-safe SQLite database manager."""

    def __init__(self, db_path: str = None) -> None:
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "data", "content.db")
        self._db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()

    def initialize(self) -> None:
        """Create the database file, tables, and indexes if they don't exist."""
        if self._db_path != ":memory:":
            db_dir = os.path.dirname(self._db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        conn = self.get_connection()
        conn.executescript(_SCHEMA_SQL)
        
        # Auto-migration for columns that may not exist in older databases
        cursor = conn.execute("PRAGMA table_info(content_items)")
        columns = [row["name"] for row in cursor.fetchall()]
        if "image_prompt" not in columns:
            conn.execute("ALTER TABLE content_items ADD COLUMN image_prompt TEXT")
        for col in ("subject", "headline", "fact_text", "highlight_1", "highlight_2", "category"):
            if col not in columns:
                conn.execute(f"ALTER TABLE content_items ADD COLUMN {col} TEXT")
            
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.commit()
        logger.info("Database initialized at %s", self._db_path)

    def get_connection(self) -> sqlite3.Connection:
        """Return a thread-local connection. Creates one if it doesn't exist."""
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            self._local.connection = conn
        return conn

    # ------------------------------------------------------------------ #
    #  content_items CRUD
    # ------------------------------------------------------------------ #

    def create_content_item(self, topic: str, **extra_fields) -> int:
        """Insert a new topic with status 'pending_approval'. Returns row id.
        
        Extra fields (subject, headline, fact_text, etc.) are passed through
        as additional column values.
        """
        cols = ["topic"]
        vals = [topic]
        for key, value in extra_fields.items():
            cols.append(key)
            vals.append(value)
        placeholders = ", ".join("?" for _ in vals)
        col_names = ", ".join(cols)
        sql = f"INSERT INTO content_items ({col_names}) VALUES ({placeholders})"

        conn = self.get_connection()
        with self._lock:
            cursor = conn.execute(sql, vals)
            conn.commit()
            item_id = cursor.lastrowid
        logger.info("Created content_item id=%d topic='%s'", item_id, topic[:60])
        return item_id

    def get_content_item(self, item_id: int) -> dict | None:
        """Fetch a single content_item by id."""
        conn = self.get_connection()
        row = conn.execute(
            "SELECT * FROM content_items WHERE id = ?", (item_id,)
        ).fetchone()
        return content_item_from_row(row)

    def get_items_by_status(self, status: str) -> list[dict]:
        """Fetch all content_items with the given status, ordered by created_at."""
        conn = self.get_connection()
        rows = conn.execute(
            "SELECT * FROM content_items WHERE status = ? ORDER BY created_at ASC",
            (status,),
        ).fetchall()
        return [content_item_from_row(r) for r in rows]

    def get_all_items(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Fetch all content_items, newest first."""
        conn = self.get_connection()
        rows = conn.execute(
            "SELECT * FROM content_items ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [content_item_from_row(r) for r in rows]

    def update_status(self, item_id: int, status: str, **fields) -> None:
        """
        Update status and any additional fields on a content_item.
        Automatically updates the 'updated_at' timestamp.
        """
        sets = ["status = ?", "updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now')"]
        values = [status]
        for key, value in fields.items():
            sets.append(f"{key} = ?")
            values.append(value)
        values.append(item_id)

        sql = f"UPDATE content_items SET {', '.join(sets)} WHERE id = ?"
        conn = self.get_connection()
        with self._lock:
            conn.execute(sql, values)
            conn.commit()
        logger.info("Updated content_item id=%d status=%s fields=%s",
                     item_id, status, list(fields.keys()))

    def set_telegram_msg(self, item_id: int, chat_id: int, msg_id: int) -> None:
        """Store Telegram message reference for later editing."""
        conn = self.get_connection()
        with self._lock:
            conn.execute(
                """UPDATE content_items
                   SET telegram_chat_id = ?, telegram_msg_id = ?,
                       updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now')
                   WHERE id = ?""",
                (chat_id, msg_id, item_id),
            )
            conn.commit()

    # ------------------------------------------------------------------ #
    #  topic_source_rows
    # ------------------------------------------------------------------ #

    def get_consumed_row_indices(self, source_file: str) -> set[int]:
        """Return the set of row_index values already consumed for a file."""
        conn = self.get_connection()
        rows = conn.execute(
            "SELECT row_index FROM topic_source_rows WHERE source_file = ? AND consumed = 1",
            (source_file,),
        ).fetchall()
        return {r["row_index"] for r in rows}

    def mark_row_consumed(
        self, source_file: str, row_index: int, topic: str, content_item_id: int
    ) -> int:
        """Insert a consumed row into topic_source_rows. Returns the new row id."""
        conn = self.get_connection()
        with self._lock:
            cursor = conn.execute(
                """INSERT INTO topic_source_rows
                   (source_file, row_index, topic, consumed, content_item_id)
                   VALUES (?, ?, ?, 1, ?)""",
                (source_file, row_index, topic, content_item_id),
            )
            conn.commit()
            return cursor.lastrowid

    def get_remaining_topic_count(self, source_file: str, total_rows: int) -> int:
        """Return how many rows from source_file have NOT been consumed."""
        conn = self.get_connection()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM topic_source_rows WHERE source_file = ? AND consumed = 1",
            (source_file,),
        ).fetchone()
        consumed = row["cnt"] if row else 0
        return max(0, total_rows - consumed)

    # ------------------------------------------------------------------ #
    #  scheduled_posts
    # ------------------------------------------------------------------ #

    def insert_scheduled_post(
        self, content_item_id: int, target_region: str, scheduled_time_utc: str
    ) -> int:
        """Insert a new scheduled_posts row. Returns the row id."""
        conn = self.get_connection()
        with self._lock:
            cursor = conn.execute(
                """INSERT INTO scheduled_posts
                   (content_item_id, target_region, scheduled_time_utc)
                   VALUES (?, ?, ?)""",
                (content_item_id, target_region, scheduled_time_utc),
            )
            conn.commit()
            return cursor.lastrowid

    def get_due_scheduled_posts(self, now_utc: str) -> list[dict]:
        """Fetch scheduled_posts where status='queued' and scheduled_time_utc <= now."""
        conn = self.get_connection()
        rows = conn.execute(
            """SELECT * FROM scheduled_posts
               WHERE status = 'queued' AND scheduled_time_utc <= ?
               ORDER BY scheduled_time_utc ASC""",
            (now_utc,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_queued_posts_in_window(self, window_start_utc: str, window_end_utc: str) -> list[dict]:
        """Fetch all queued/posted scheduled_posts in a time window."""
        conn = self.get_connection()
        rows = conn.execute(
            """SELECT * FROM scheduled_posts
               WHERE status IN ('queued', 'posted')
                 AND scheduled_time_utc >= ? AND scheduled_time_utc <= ?
               ORDER BY scheduled_time_utc ASC""",
            (window_start_utc, window_end_utc),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_scheduled_post_status(self, post_id: int, status: str) -> None:
        """Update the status of a scheduled_posts row."""
        conn = self.get_connection()
        with self._lock:
            conn.execute(
                "UPDATE scheduled_posts SET status = ? WHERE id = ?",
                (status, post_id),
            )
            conn.commit()

    # ------------------------------------------------------------------ #
    #  usage_log
    # ------------------------------------------------------------------ #

    def log_usage(
        self,
        provider: str,
        endpoint: str,
        credit_cost: float = 0,
        success: bool = True,
        error_msg: str | None = None,
    ) -> None:
        """Insert a row into the usage_log table."""
        conn = self.get_connection()
        with self._lock:
            conn.execute(
                """INSERT INTO usage_log (provider, endpoint, credit_cost, success, error_msg)
                   VALUES (?, ?, ?, ?, ?)""",
                (provider, endpoint, credit_cost, 1 if success else 0, error_msg),
            )
            conn.commit()

    def get_usage_logs(
        self, provider: str | None = None, limit: int = 200
    ) -> list[dict]:
        """Fetch usage_log entries, newest first. Optionally filter by provider."""
        conn = self.get_connection()
        if provider:
            rows = conn.execute(
                "SELECT * FROM usage_log WHERE provider = ? ORDER BY timestamp DESC LIMIT ?",
                (provider, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM usage_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
