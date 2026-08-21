import io

import pytest

from hearthview.storage import ArtifactPathError, ArtifactStore, ArtifactTooLarge


def test_artifact_install_is_content_addressed_and_deduplicated(artifact_store: ArtifactStore) -> None:
    first = artifact_store.install(io.BytesIO(b"same source bytes"))
    second = artifact_store.install(io.BytesIO(b"same source bytes"))

    assert first.sha256 == second.sha256
    assert first.path == second.path
    assert first.path.read_bytes() == b"same source bytes"
    assert len(tuple(artifact_store.root.rglob(first.sha256))) == 1


def test_artifact_lookup_rejects_path_like_hashes(artifact_store: ArtifactStore) -> None:
    with pytest.raises(ArtifactPathError, match="64 lowercase hexadecimal"):
        artifact_store.resolve("../../private-plan.pdf")


def test_failed_stream_does_not_leave_partial_artifact(artifact_store: ArtifactStore) -> None:
    class BrokenStream(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            if self.tell() > 0:
                raise OSError("source disconnected")
            return super().read(4)

    with pytest.raises(OSError, match="disconnected"):
        artifact_store.install(BrokenStream(b"partial source"))

    assert not tuple(artifact_store.root.rglob("*.partial"))


def test_stream_limit_stops_before_installing_oversized_artifact(
    artifact_store: ArtifactStore,
) -> None:
    with pytest.raises(ArtifactTooLarge):
        artifact_store.install(io.BytesIO(b"too large"), max_bytes=4)

    assert not tuple(path for path in artifact_store.root.rglob("*") if path.is_file())
