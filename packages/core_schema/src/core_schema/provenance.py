"""Universal provenance and epistemic-state records (plan §5.2).

Every entity in the canonical model carries a Provenance record. This is
what makes an AI proposal into an auditable, revocable claim instead of a
silent fact: nothing is geometry until a human — or an explicit, logged
auto-approval policy — moves it from PROPOSED to USER_CONFIRMED.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SourceKind(str, Enum):
    PATH = "path"
    SPAN = "span"
    IMAGE = "image"
    USER = "user"


class ProvenanceState(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    PROPOSED = "PROPOSED"
    USER_CONFIRMED = "USER_CONFIRMED"
    USER_AUTHORED = "USER_AUTHORED"
    REJECTED = "REJECTED"


class ProvenanceBasis(str, Enum):
    EXPLICIT_DIMENSION = "explicit_dimension"
    MEASURED_FROM_GEOMETRY = "measured_from_geometry"
    INHERITED_FROM_LEVEL = "inherited_from_level"
    READ_FROM_SECTION = "read_from_section"
    ASSUMED_DEFAULT = "assumed_default"
    UNKNOWN = "unknown"


# Honest tolerance bands (plan §2, §17): explicit dimensions get 1 inch,
# geometry measured off linework never claims better than 1/2 inch.
TOLERANCE_EXPLICIT_NM = 25_400_000  # 1 in
TOLERANCE_MEASURED_NM = 12_700_000  # 1/2 in


@dataclass(frozen=True, slots=True)
class SourceRef:
    doc_id: str
    page: int
    kind: SourceKind
    path_uids: tuple[str, ...] = ()
    region_id: str | None = None
    bbox_sheet: tuple[float, float, float, float] | None = None
    extractor_version: str = ""

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "page": self.page,
            "kind": self.kind.value,
            "path_uids": list(self.path_uids),
            "region_id": self.region_id,
            "bbox_sheet": list(self.bbox_sheet) if self.bbox_sheet else None,
            "extractor_version": self.extractor_version,
        }

    @staticmethod
    def from_dict(d: dict) -> "SourceRef":
        return SourceRef(
            doc_id=d["doc_id"],
            page=d["page"],
            kind=SourceKind(d["kind"]),
            path_uids=tuple(d.get("path_uids") or ()),
            region_id=d.get("region_id"),
            bbox_sheet=tuple(d["bbox_sheet"]) if d.get("bbox_sheet") else None,
            extractor_version=d.get("extractor_version", ""),
        )


@dataclass(frozen=True, slots=True)
class Provenance:
    state: ProvenanceState
    basis: ProvenanceBasis
    tolerance_nm: int
    created_by: str
    confidence: float | None = None
    source_refs: tuple[SourceRef, ...] = ()

    def __post_init__(self) -> None:
        is_user_state = self.state in (ProvenanceState.USER_CONFIRMED, ProvenanceState.USER_AUTHORED)
        if is_user_state and self.confidence is not None:
            raise ValueError(f"confidence must be null for state={self.state.value}")
        if not is_user_state and self.confidence is None and self.state != ProvenanceState.OBSERVED:
            raise ValueError(f"confidence is required for state={self.state.value}")
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0,1], got {self.confidence}")
        if self.tolerance_nm < 0:
            raise ValueError("tolerance_nm must be non-negative")
        # §12 check 10 (invention audit): every non-user-authored entity must
        # cite at least one non-user source.
        if self.state != ProvenanceState.USER_AUTHORED and not self.source_refs:
            raise ValueError(
                f"state={self.state.value} requires at least one source_ref "
                "(invention audit, plan §12 check 10)"
            )

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "basis": self.basis.value,
            "tolerance_nm": self.tolerance_nm,
            "created_by": self.created_by,
            "confidence": self.confidence,
            "source_refs": [r.to_dict() for r in self.source_refs],
        }

    @staticmethod
    def from_dict(d: dict) -> "Provenance":
        return Provenance(
            state=ProvenanceState(d["state"]),
            basis=ProvenanceBasis(d["basis"]),
            tolerance_nm=d["tolerance_nm"],
            created_by=d["created_by"],
            confidence=d.get("confidence"),
            source_refs=tuple(SourceRef.from_dict(r) for r in d.get("source_refs", [])),
        )


def user_authored(created_by: str) -> Provenance:
    """Shorthand for the provenance of an entity a human drew from scratch."""
    return Provenance(
        state=ProvenanceState.USER_AUTHORED,
        basis=ProvenanceBasis.UNKNOWN,
        tolerance_nm=TOLERANCE_EXPLICIT_NM,
        created_by=created_by,
        confidence=None,
        source_refs=(),
    )


def user_confirmed(
    basis: ProvenanceBasis, tolerance_nm: int, created_by: str, source_refs: tuple[SourceRef, ...]
) -> Provenance:
    """Shorthand for the provenance of a proposal a human approved unchanged."""
    return Provenance(
        state=ProvenanceState.USER_CONFIRMED,
        basis=basis,
        tolerance_nm=tolerance_nm,
        created_by=created_by,
        confidence=None,
        source_refs=source_refs,
    )
