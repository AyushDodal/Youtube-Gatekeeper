"""Small synchronous SQLite store. All timestamps are timezone-aware UTC ISO strings."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from backend.db.models import SCHEMA


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.connection = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
        self.connection.row_factory = sqlite3.Row
        try:
            self.connection.execute("PRAGMA journal_mode = WAL")
            self.connection.execute("PRAGMA synchronous = FULL")
            self.connection.executescript(SCHEMA)
        except sqlite3.Error:
            self.connection.close()
            raise

    def close(self):
        with self.lock:
            self.connection.close()

    def get_or_create_conversation(self, conversation_id: str | None = None) -> dict:
        with self.lock, self.connection:
            if conversation_id:
                row = self.connection.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
                if row is None:
                    raise KeyError("Conversation not found.")
                return dict(row)
            now = utcnow().isoformat()
            identifier = str(uuid4())
            self.connection.execute("INSERT INTO conversations(id,created_at,updated_at) VALUES (?,?,?)", (identifier, now, now))
            return {"id": identifier, "created_at": now, "updated_at": now, "status": "open"}

    def close_conversation(self, conversation_id: str):
        with self.lock, self.connection:
            self.connection.execute("UPDATE conversations SET status='closed',updated_at=? WHERE id=?", (utcnow().isoformat(), conversation_id))

    def add_message(self, conversation_id: str, role: str, content: str) -> dict:
        now = utcnow().isoformat()
        with self.lock, self.connection:
            cursor = self.connection.execute("INSERT INTO messages(conversation_id,role,content,created_at) VALUES (?,?,?,?)", (conversation_id, role, content, now))
            self.connection.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id))
            return {"id": cursor.lastrowid, "conversation_id": conversation_id, "role": role, "content": content, "created_at": now}

    def get_messages(self, conversation_id: str) -> list[dict]:
        with self.lock:
            return [dict(row) for row in self.connection.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (conversation_id,))]

    def active_session(self) -> dict | None:
        with self.lock:
            row = self.connection.execute("SELECT * FROM youtube_sessions WHERE status='active'").fetchone()
            return dict(row) if row else None

    def create_session(self, *, conversation_id: str, reason: str, started_at: datetime, expires_at: datetime, duration_minutes: int) -> dict:
        session = {"id": str(uuid4()), "conversation_id": conversation_id, "reason": reason,
                   "started_at": started_at.isoformat(), "expires_at": expires_at.isoformat(),
                   "duration_minutes": duration_minutes, "status": "active", "ended_at": None}
        with self.lock, self.connection:
            self.connection.execute("""INSERT INTO youtube_sessions
                (id,conversation_id,reason,started_at,expires_at,duration_minutes,status)
                VALUES (:id,:conversation_id,:reason,:started_at,:expires_at,:duration_minutes,:status)""", session)
        return session

    def finish_session(self, session: dict, status: str, ended_at: datetime):
        start = datetime.fromisoformat(session["started_at"])
        end = max(start, min(ended_at, datetime.fromisoformat(session["expires_at"])))
        with self.lock, self.connection:
            changed = self.connection.execute("UPDATE youtube_sessions SET status=?,ended_at=? WHERE id=? AND status='active'", (status, end.isoformat(), session["id"])).rowcount
            if changed and status != "failed":
                self.connection.execute("INSERT OR IGNORE INTO usage_log(session_id,started_at,ended_at,duration_minutes) VALUES (?,?,?,?)", (session["id"], start.isoformat(), end.isoformat(), (end-start).total_seconds()/60))

    def sessions(self, limit: int | None = None) -> list[dict]:
        with self.lock:
            sql = "SELECT * FROM youtube_sessions ORDER BY started_at DESC"
            rows = self.connection.execute(sql + " LIMIT ?", (limit,)) if limit else self.connection.execute(sql)
            return [dict(row) for row in rows]
