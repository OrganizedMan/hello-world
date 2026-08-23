from pathlib import Path

from ingest import PyMuPdfBackend

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures/garrigan-261-grove/source/garrigan-main-set.pdf"


def test_raw_paths_reproduces_known_wall_polygon():
    # The mudroom's new north wall poché (Appendix A: 9.01 pt thick = 6.0 in
    # exactly). Reproduced here as a harness golden value, not re-derived.
    with PyMuPdfBackend().open(str(FIXTURE)) as h:
        paths = h.raw_paths(1)
    assert len(paths) == 9789
    first = paths[0]
    assert first.kind == "fill"
    assert first.fill_rgb is not None
    assert len(first.points) >= 4


def test_raw_text_spans_finds_the_tv_annotation():
    with PyMuPdfBackend().open(str(FIXTURE)) as h:
        spans = h.raw_text_spans(1)
    tv = [s for s in spans if s.text == '60" TV']
    assert len(tv) == 1
    x0, y0, x1, y1 = tv[0].bbox
    # Appendix A: text bbox [1962.59, 725.62, 1972.35, 751.15] (measured by
    # a different code path during planning) — assert close agreement, not
    # bit-identical, since that figure was read off a rendering, not this
    # exact API.
    assert abs(x0 - 1962.59) < 1.0
    assert abs(y1 - 751.15) < 1.0
    assert tv[0].direction == (0.0, -1.0)


def test_raw_paths_and_spans_are_page_scoped():
    with PyMuPdfBackend().open(str(FIXTURE)) as h:
        a0_paths = h.raw_paths(0)
        a1_paths = h.raw_paths(1)
    assert len(a0_paths) != len(a1_paths)
