import pytest

from core_schema import (
    Provenance,
    ProvenanceBasis,
    ProvenanceState,
    SourceKind,
    SourceRef,
    TOLERANCE_EXPLICIT_NM,
    user_authored,
    user_confirmed,
)


def make_ref():
    return SourceRef(doc_id="doc1", page=2, kind=SourceKind.PATH, path_uids=("abc123",))


def test_user_authored_has_no_confidence_and_no_source_required():
    p = user_authored(created_by="user:jhmgarrigan")
    assert p.state == ProvenanceState.USER_AUTHORED
    assert p.confidence is None
    assert p.source_refs == ()


def test_proposed_requires_confidence():
    with pytest.raises(ValueError):
        Provenance(
            state=ProvenanceState.PROPOSED,
            basis=ProvenanceBasis.MEASURED_FROM_GEOMETRY,
            tolerance_nm=TOLERANCE_EXPLICIT_NM,
            created_by="extractor@0.1.0",
            confidence=None,
            source_refs=(make_ref(),),
        )


def test_proposed_requires_source_ref_invention_audit():
    with pytest.raises(ValueError):
        Provenance(
            state=ProvenanceState.PROPOSED,
            basis=ProvenanceBasis.MEASURED_FROM_GEOMETRY,
            tolerance_nm=TOLERANCE_EXPLICIT_NM,
            created_by="extractor@0.1.0",
            confidence=0.9,
            source_refs=(),
        )


def test_user_confirmed_rejects_confidence():
    with pytest.raises(ValueError):
        Provenance(
            state=ProvenanceState.USER_CONFIRMED,
            basis=ProvenanceBasis.EXPLICIT_DIMENSION,
            tolerance_nm=TOLERANCE_EXPLICIT_NM,
            created_by="user:jhmgarrigan",
            confidence=0.5,
            source_refs=(make_ref(),),
        )


def test_confidence_out_of_range_rejected():
    with pytest.raises(ValueError):
        Provenance(
            state=ProvenanceState.PROPOSED,
            basis=ProvenanceBasis.MEASURED_FROM_GEOMETRY,
            tolerance_nm=TOLERANCE_EXPLICIT_NM,
            created_by="vlm-proposer@0.1.0",
            confidence=1.5,
            source_refs=(make_ref(),),
        )


def test_negative_tolerance_rejected():
    with pytest.raises(ValueError):
        Provenance(
            state=ProvenanceState.OBSERVED,
            basis=ProvenanceBasis.UNKNOWN,
            tolerance_nm=-1,
            created_by="extractor@0.1.0",
            source_refs=(make_ref(),),
        )


def test_roundtrip_to_from_dict():
    p = user_confirmed(
        basis=ProvenanceBasis.EXPLICIT_DIMENSION,
        tolerance_nm=TOLERANCE_EXPLICIT_NM,
        created_by="user:jhmgarrigan",
        source_refs=(make_ref(),),
    )
    d = p.to_dict()
    p2 = Provenance.from_dict(d)
    assert p2 == p
