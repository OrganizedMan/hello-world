"""The project file: a single local SQLite database (plan §5.2, §15).

Two things live here at Sprint 1: content-addressed source documents (the
PDFs themselves, deduplicated by sha256, so re-importing the same file is
a no-op and every entity's SourceRef.doc_id can be trusted to name exactly
one set of bytes forever), and the approval-script log (every human
decision, in order, replayable — this is what makes "how much correction
was required" measurable in §17 and what the Tier-7 test harness in §16
replays).

No project-entity tables yet (Level, WallSegment, ...): those arrive with
the constraint solver and authoring UI in Sprint 2, once there is
something to persist beyond source documents.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_documents (
    id         TEXT PRIMARY KEY,
    filename   TEXT NOT NULL,
    sha256     TEXT NOT NULL UNIQUE,
    page_count INTEGER NOT NULL,
    is_vector  INTEGER NOT NULL,
    bytes      BLOB NOT NULL,
    added_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approval_log (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    actor        TEXT NOT NULL,
    action       TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class SourceDocumentRow:
    id: str
    filename: str
    sha256: str
    page_count: int
    is_vector: bool
    added_at: str


@dataclass(frozen=True, slots=True)
class ApprovalLogEntry:
    seq: int
    ts: str
    actor: str
    action: str
    payload: dict


class ProjectStore:
    """Owns one project .g3d SQLite file. Not thread-safe; one writer at a time."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @classmethod
    def create(cls, path: str | Path) -> "ProjectStore":
        path = Path(path)
        if path.exists():
            raise FileExistsError(f"project store already exists at {path}")
        conn = sqlite3.connect(str(path))
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        conn.commit()
        return cls(conn)

    @classmethod
    def open(cls, path: str | Path) -> "ProjectStore":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"no project store at {path}")
        conn = sqlite3.connect(str(path))
        row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row is None:
            raise ValueError(f"{path} is not a valid project store (no schema_version)")
        version = int(row[0])
        if version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version {version}, expected {SCHEMA_VERSION}")
        return cls(conn)

    @classmethod
    def open_in_memory(cls) -> "ProjectStore":
        conn = sqlite3.connect(":memory:")
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        conn.commit()
        return cls(conn)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "ProjectStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- source documents (content-addressed) ---

    def add_source_document(
        self, filename: str, data: bytes, page_count: int, is_vector: bool
    ) -> SourceDocumentRow:
        """Idempotent by content: re-adding identical bytes returns the
        existing row rather than creating a duplicate."""
        sha256 = hashlib.sha256(data).hexdigest()
        existing = self._conn.execute(
            "SELECT id, filename, sha256, page_count, is_vector, added_at "
            "FROM source_documents WHERE sha256 = ?",
            (sha256,),
        ).fetchone()
        if existing is not None:
            return SourceDocumentRow(
                id=existing[0], filename=existing[1], sha256=existing[2],
                page_count=existing[3], is_vector=bool(existing[4]), added_at=existing[5],
            )

        doc_id = sha256[:16]
        added_at = _now_iso()
        self._conn.execute(
            "INSERT INTO source_documents "
            "(id, filename, sha256, page_count, is_vector, bytes, added_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc_id, filename, sha256, page_count, int(is_vector), data, added_at),
        )
        self._conn.commit()
        return SourceDocumentRow(
            id=doc_id, filename=filename, sha256=sha256,
            page_count=page_count, is_vector=is_vector, added_at=added_at,
        )

    def get_source_document(self, doc_id: str) -> SourceDocumentRow | None:
        row = self._conn.execute(
            "SELECT id, filename, sha256, page_count, is_vector, added_at "
            "FROM source_documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
        if row is None:
            return None
        return SourceDocumentRow(
            id=row[0], filename=row[1], sha256=row[2],
            page_count=row[3], is_vector=bool(row[4]), added_at=row[5],
        )

    def get_source_document_bytes(self, doc_id: str) -> bytes | None:
        row = self._conn.execute(
            "SELECT bytes FROM source_documents WHERE id = ?", (doc_id,)
        ).fetchone()
        return None if row is None else row[0]

    def list_source_documents(self) -> list[SourceDocumentRow]:
        rows = self._conn.execute(
            "SELECT id, filename, sha256, page_count, is_vector, added_at "
            "FROM source_documents ORDER BY added_at"
        ).fetchall()
        return [
            SourceDocumentRow(
                id=r[0], filename=r[1], sha256=r[2],
                page_count=r[3], is_vector=bool(r[4]), added_at=r[5],
            )
            for r in rows
        ]

    # --- approval-script log ---

    def log_approval(self, actor: str, action: str, payload: dict) -> int:
        ts = _now_iso()
        cur = self._conn.execute(
            "INSERT INTO approval_log (ts, actor, action, payload_json) VALUES (?, ?, ?, ?)",
            (ts, actor, action, json.dumps(payload, sort_keys=True)),
        )
        self._conn.commit()
        return cur.lastrowid

    def read_approval_log(self) -> list[ApprovalLogEntry]:
        rows = self._conn.execute(
            "SELECT seq, ts, actor, action, payload_json FROM approval_log ORDER BY seq"
        ).fetchall()
        return [
            ApprovalLogEntry(seq=r[0], ts=r[1], actor=r[2], action=r[3], payload=json.loads(r[4]))
            for r in rows
        ]


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
