import pytest

from store import ProjectStore


def test_create_rejects_existing_path(tmp_path):
    p = tmp_path / "proj.g3d"
    ProjectStore.create(p).close()
    with pytest.raises(FileExistsError):
        ProjectStore.create(p)


def test_open_rejects_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        ProjectStore.open(tmp_path / "nope.g3d")


def test_open_rejects_non_project_file(tmp_path):
    p = tmp_path / "not_a_project.g3d"
    p.write_bytes(b"garbage")
    with pytest.raises(Exception):
        ProjectStore.open(p)


def test_create_then_reopen_roundtrip(tmp_path):
    p = tmp_path / "proj.g3d"
    with ProjectStore.create(p) as store:
        doc = store.add_source_document("a.pdf", b"pdf-bytes-1", page_count=4, is_vector=True)
        doc_id = doc.id

    with ProjectStore.open(p) as store:
        got = store.get_source_document(doc_id)
        assert got is not None
        assert got.filename == "a.pdf"
        assert got.page_count == 4
        assert got.is_vector is True
        assert store.get_source_document_bytes(doc_id) == b"pdf-bytes-1"


def test_source_document_is_content_addressed_and_deduplicates():
    store = ProjectStore.open_in_memory()
    d1 = store.add_source_document("first-name.pdf", b"same-bytes", page_count=1, is_vector=True)
    d2 = store.add_source_document("different-name.pdf", b"same-bytes", page_count=1, is_vector=True)
    assert d1.id == d2.id
    assert len(store.list_source_documents()) == 1
    # original filename wins; the id names the content, not the label
    assert store.get_source_document(d1.id).filename == "first-name.pdf"


def test_different_bytes_get_different_ids():
    store = ProjectStore.open_in_memory()
    d1 = store.add_source_document("a.pdf", b"bytes-a", page_count=1, is_vector=True)
    d2 = store.add_source_document("b.pdf", b"bytes-b", page_count=1, is_vector=True)
    assert d1.id != d2.id
    assert len(store.list_source_documents()) == 2


def test_approval_log_is_ordered_and_replayable():
    store = ProjectStore.open_in_memory()
    store.log_approval("user:jhmgarrigan", "confirm_wall", {"wall_id": "W1"})
    store.log_approval("user:jhmgarrigan", "edit_dimension", {"dim_id": "D1", "value_nm": 12700000})
    store.log_approval("extractor@0.1.0", "propose_wall", {"wall_id": "W2"})

    log = store.read_approval_log()
    assert [e.action for e in log] == ["confirm_wall", "edit_dimension", "propose_wall"]
    assert [e.seq for e in log] == sorted(e.seq for e in log)
    assert log[1].payload == {"dim_id": "D1", "value_nm": 12700000}


def test_get_missing_source_document_returns_none():
    store = ProjectStore.open_in_memory()
    assert store.get_source_document("nonexistent") is None
