from pathlib import Path

from ingest import PyMuPdfBackend
from extract import harvest_paths, harvest_text_lines

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures/garrigan-261-grove/source/garrigan-main-set.pdf"


def test_path_uid_is_stable_across_reharvest():
    with PyMuPdfBackend().open(str(FIXTURE)) as h:
        first = harvest_paths(h, 1)
        second = harvest_paths(h, 1)
    assert [p.path_uid for p in first] == [p.path_uid for p in second]


def test_path_uid_differs_between_distinct_paths():
    with PyMuPdfBackend().open(str(FIXTURE)) as h:
        paths = harvest_paths(h, 1)
    uids = [p.path_uid for p in paths]
    assert len(set(uids)) > len(uids) * 0.99  # collisions should be essentially nonexistent


def test_text_mask_suppression_drops_pure_white_fills():
    with PyMuPdfBackend().open(str(FIXTURE)) as h:
        with_masks = harvest_paths(h, 1, suppress_text_masks=False)
        without_masks = harvest_paths(h, 1, suppress_text_masks=True)
    assert len(without_masks) < len(with_masks)
    assert all(p.fill_rgb != (1.0, 1.0, 1.0) for p in without_masks if p.kind == "fill")


def test_harvest_text_lines_returns_every_span():
    with PyMuPdfBackend().open(str(FIXTURE)) as h:
        spans = harvest_text_lines(h, 1)
    assert len(spans) == 209  # Appendix A: 209 text spans on A-1
