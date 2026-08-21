from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field

from hearthview.canonical import canonical_bytes
from hearthview.fixture import build_a1_fixture
from hearthview.models import FrozenModel, Island, ProjectModel, ReviewDecision, ReviewState, SourceDocument
from hearthview.units import parse_length


EventOperation = Literal[
    "APPROVE_REVIEW",
    "EDIT_AND_APPROVE",
    "REJECT_REVIEW",
    "REVERT_EVENT",
]


class RevisionConflict(RuntimeError):
    """Raised when an edit is based on an outdated project revision."""


class ModelEvent(FrozenModel):
    id: str
    operation: EventOperation
    item_id: str | None = None
    payload: dict[str, str | int] = Field(default_factory=dict)
    source_ref_ids: tuple[str, ...] = ()
    rationale: str


@dataclass(frozen=True)
class ProjectRecord:
    id: str
    name: str
    revision: int


@dataclass(frozen=True)
class SourceRecord:
    id: str
    project_id: str
    display_name: str
    sha256: str
    byte_count: int
    page_count: int
    profile: str


@dataclass(frozen=True)
class GeometryRecord:
    artifact_id: str
    project_id: str
    model_hash: str
    geometry_hash: str
    glb_file_hash: str
    primitive_count: int
    bounds_ticks: tuple[int, int, int, int, int, int]


class ProjectRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS model_events (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id),
                    revision INTEGER NOT NULL,
                    operation TEXT NOT NULL,
                    item_id TEXT,
                    payload_json BLOB NOT NULL,
                    source_ref_ids_json BLOB NOT NULL,
                    rationale TEXT NOT NULL,
                    UNIQUE(project_id, revision)
                );
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id),
                    display_name TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    byte_count INTEGER NOT NULL,
                    page_count INTEGER NOT NULL,
                    profile TEXT NOT NULL DEFAULT 'UNSUPPORTED',
                    UNIQUE(project_id, sha256)
                );
                CREATE TABLE IF NOT EXISTS geometry_artifacts (
                    artifact_id TEXT NOT NULL,
                    project_id TEXT NOT NULL REFERENCES projects(id),
                    model_hash TEXT NOT NULL,
                    geometry_hash TEXT NOT NULL,
                    glb_file_hash TEXT NOT NULL,
                    primitive_count INTEGER NOT NULL,
                    bounds_ticks_json BLOB NOT NULL,
                    PRIMARY KEY(project_id, artifact_id)
                );
                """
            )
            source_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(sources)").fetchall()
            }
            if "profile" not in source_columns:
                connection.execute(
                    "ALTER TABLE sources ADD COLUMN profile TEXT NOT NULL DEFAULT 'UNSUPPORTED'"
                )

    def create(self, name: str, project_id: str | None = None) -> ProjectRecord:
        resolved_id = project_id or str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO projects(id, name, revision) VALUES (?, ?, 0)",
                (resolved_id, name),
            )
        return ProjectRecord(id=resolved_id, name=name, revision=0)

    def get(self, project_id: str) -> ProjectRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, name, revision FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise KeyError(project_id)
        return ProjectRecord(id=row["id"], name=row["name"], revision=row["revision"])

    def add_source(
        self,
        project_id: str,
        display_name: str,
        sha256: str,
        byte_count: int,
        page_count: int,
        profile: str = "UNSUPPORTED",
        source_id: str | None = None,
    ) -> SourceRecord:
        self.get(project_id)
        resolved_id = source_id or str(uuid.uuid4())
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM sources WHERE project_id = ? AND sha256 = ?",
                (project_id, sha256),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO sources(
                        id, project_id, display_name, sha256, byte_count, page_count
                        , profile
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (resolved_id, project_id, display_name, sha256, byte_count, page_count, profile),
                )
                return SourceRecord(
                    id=resolved_id,
                    project_id=project_id,
                    display_name=display_name,
                    sha256=sha256,
                    byte_count=byte_count,
                    page_count=page_count,
                    profile=profile,
                )
        return SourceRecord(
            id=existing["id"],
            project_id=existing["project_id"],
            display_name=existing["display_name"],
            sha256=existing["sha256"],
            byte_count=existing["byte_count"],
            page_count=existing["page_count"],
            profile=existing["profile"],
        )

    def mark_source_profile(self, sha256: str, profile: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE sources SET profile = ? WHERE sha256 = ?",
                (profile, sha256),
            )

    def get_source(self, project_id: str, source_id: str) -> SourceRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sources WHERE project_id = ? AND id = ?",
                (project_id, source_id),
            ).fetchone()
        if row is None:
            raise KeyError(source_id)
        return SourceRecord(
            id=row["id"],
            project_id=row["project_id"],
            display_name=row["display_name"],
            sha256=row["sha256"],
            byte_count=row["byte_count"],
            page_count=row["page_count"],
            profile=row["profile"],
        )

    def list_sources(self, project_id: str) -> tuple[SourceRecord, ...]:
        self.get(project_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM sources WHERE project_id = ? ORDER BY rowid",
                (project_id,),
            ).fetchall()
        return tuple(
            SourceRecord(
                id=row["id"],
                project_id=row["project_id"],
                display_name=row["display_name"],
                sha256=row["sha256"],
                byte_count=row["byte_count"],
                page_count=row["page_count"],
                profile=row["profile"],
            )
            for row in rows
        )

    def add_geometry(
        self,
        *,
        project_id: str,
        artifact_id: str,
        model_hash: str,
        geometry_hash: str,
        glb_file_hash: str,
        primitive_count: int,
        bounds_ticks: tuple[int, int, int, int, int, int],
    ) -> GeometryRecord:
        self.get(project_id)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO geometry_artifacts(
                    artifact_id, project_id, model_hash, geometry_hash,
                    glb_file_hash, primitive_count, bounds_ticks_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    project_id,
                    model_hash,
                    geometry_hash,
                    glb_file_hash,
                    primitive_count,
                    canonical_bytes(bounds_ticks),
                ),
            )
        return GeometryRecord(
            artifact_id=artifact_id,
            project_id=project_id,
            model_hash=model_hash,
            geometry_hash=geometry_hash,
            glb_file_hash=glb_file_hash,
            primitive_count=primitive_count,
            bounds_ticks=bounds_ticks,
        )

    def get_geometry(self, project_id: str, artifact_id: str) -> GeometryRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM geometry_artifacts
                WHERE project_id = ? AND artifact_id = ?
                """,
                (project_id, artifact_id),
            ).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        bounds = tuple(int(value) for value in json.loads(row["bounds_ticks_json"]))
        return GeometryRecord(
            artifact_id=row["artifact_id"],
            project_id=row["project_id"],
            model_hash=row["model_hash"],
            geometry_hash=row["geometry_hash"],
            glb_file_hash=row["glb_file_hash"],
            primitive_count=row["primitive_count"],
            bounds_ticks=bounds,  # type: ignore[arg-type]
        )

    def latest_geometry(
        self,
        project_id: str,
        model_hash: str | None = None,
    ) -> GeometryRecord | None:
        self.get(project_id)
        with self._connect() as connection:
            if model_hash is None:
                row = connection.execute(
                    """
                    SELECT artifact_id FROM geometry_artifacts
                    WHERE project_id = ? ORDER BY rowid DESC LIMIT 1
                    """,
                    (project_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT artifact_id FROM geometry_artifacts
                    WHERE project_id = ? AND model_hash = ?
                    ORDER BY rowid DESC LIMIT 1
                    """,
                    (project_id, model_hash),
                ).fetchone()
        return self.get_geometry(project_id, row["artifact_id"]) if row is not None else None

    def append_event(self, project_id: str, base_revision: int, event: ModelEvent) -> int:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT revision FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if row is None:
                raise KeyError(project_id)
            current_revision = int(row["revision"])
            if current_revision != base_revision:
                raise RevisionConflict(
                    f"This edit was based on revision {base_revision}; current revision is {current_revision}."
                )
            revision = current_revision + 1
            connection.execute(
                """
                INSERT INTO model_events(
                    id, project_id, revision, operation, item_id, payload_json,
                    source_ref_ids_json, rationale
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    project_id,
                    revision,
                    event.operation,
                    event.item_id,
                    canonical_bytes(event.payload),
                    canonical_bytes(event.source_ref_ids),
                    event.rationale,
                ),
            )
            connection.execute(
                "UPDATE projects SET revision = ? WHERE id = ?",
                (revision, project_id),
            )
        return revision

    def revert_event(
        self,
        project_id: str,
        base_revision: int,
        target_event_id: str,
        event_id: str | None = None,
    ) -> int:
        return self.append_event(
            project_id,
            base_revision,
            ModelEvent(
                id=event_id or f"revert-{target_event_id}",
                operation="REVERT_EVENT",
                payload={"target_event_id": target_event_id},
                rationale="Homeowner undid the previous review decision.",
            ),
        )

    def list_events(self, project_id: str) -> tuple[ModelEvent, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, operation, item_id, payload_json, source_ref_ids_json, rationale
                FROM model_events WHERE project_id = ? ORDER BY revision
                """,
                (project_id,),
            ).fetchall()
        return tuple(
            ModelEvent(
                id=row["id"],
                operation=row["operation"],
                item_id=row["item_id"],
                payload=json.loads(row["payload_json"]),
                source_ref_ids=tuple(json.loads(row["source_ref_ids_json"])),
                rationale=row["rationale"],
            )
            for row in rows
        )

    def replay(self, project_id: str) -> ProjectModel:
        project = self.get(project_id)
        sources = self.list_sources(project_id)
        events = self.list_events(project_id)
        reverted = {
            str(event.payload["target_event_id"])
            for event in events
            if event.operation == "REVERT_EVENT"
        }
        primary_source = sources[0] if sources else None
        source_document = (
            SourceDocument(
                id=primary_source.id,
                display_name=primary_source.display_name,
                sha256=primary_source.sha256,
                page_count=primary_source.page_count,
                profile=primary_source.profile,
            )
            if primary_source is not None
            else None
        )
        model = build_a1_fixture(source_document).model_copy(
            update={"id": project.id, "name": project.name, "revision": project.revision}
        )
        for event in events:
            if event.operation == "REVERT_EVENT" or event.id in reverted:
                continue
            model = _apply_event(model, event)
        return model


def _apply_event(model: ProjectModel, event: ModelEvent) -> ProjectModel:
    if event.item_id is None:
        return model
    state = {
        "APPROVE_REVIEW": ReviewState.APPROVED,
        "EDIT_AND_APPROVE": ReviewState.EDITED_APPROVED,
        "REJECT_REVIEW": ReviewState.REJECTED,
    }[event.operation]
    decisions = tuple(
        ReviewDecision(item_id=decision.item_id, state=state)
        if decision.item_id == event.item_id
        else decision
        for decision in model.review_decisions
    )
    updates: dict[str, object] = {"review_decisions": decisions}
    if (
        event.operation == "EDIT_AND_APPROVE"
        and event.item_id == "review_a1_island"
        and model.island is not None
    ):
        width = event.payload.get("width")
        depth = event.payload.get("depth")
        if not isinstance(width, str) or not isinstance(depth, str):
            raise ValueError("Island edits require labeled width and depth values.")
        updates["island"] = Island.model_validate(
            {
                **model.island.model_dump(),
                "width_ticks": parse_length(width),
                "depth_ticks": parse_length(depth),
            }
        )
    return model.model_copy(update=updates)
