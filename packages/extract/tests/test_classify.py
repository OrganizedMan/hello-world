from extract.classify import TextClass, classify_text_line, reassemble_lines
from extract.harvest import HarvestedText


def span(text, x0, y0, x1, y1, direction=(1.0, 0.0), page_index=1, color=(0.0, 0.0, 1.0)):
    return HarvestedText(
        page_index=page_index, text=text, bbox=(x0, y0, x1, y1),
        size_pt=8.5, color_rgb=color, font="ArialMT", direction=direction,
    )


def test_clg_ht_false_positive_is_excluded_even_though_it_contains_a_valid_token():
    # The exact known false-positive from Appendix A.
    line = reassemble_lines([span('CLG HT - 8\'  5"', 0, 0, 60, 10)])[0]
    assert classify_text_line(line) == TextClass.CEILING_HEIGHT_TAG


def test_bare_dimension_string_classifies_as_dimension():
    line = reassemble_lines([span('5\' - 0"', 0, 0, 20, 10)])[0]
    assert classify_text_line(line) == TextClass.DIMENSION_STRING


def test_room_label_is_other():
    line = reassemble_lines([span("MUDROOM", 0, 0, 50, 10)])[0]
    assert classify_text_line(line) == TextClass.OTHER


def test_split_spans_on_same_baseline_reassemble_into_one_line():
    # "CLG HT - 8'" and " 5\"" as two separate spans, as they can arrive
    # from the PDF's text extraction (plan §6 step 5).
    spans = [
        span("CLG HT - 8'", 100, 50, 140, 60),
        span(' 5"', 140, 50, 150, 60),
    ]
    lines = reassemble_lines(spans)
    assert len(lines) == 1
    assert lines[0].text == "CLG HT - 8' 5\""
    assert classify_text_line(lines[0]) == TextClass.CEILING_HEIGHT_TAG


def test_far_apart_spans_on_same_baseline_do_not_merge():
    spans = [
        span("3' - 1\"", 100, 50, 120, 60),
        span("5' - 0\"", 400, 50, 420, 60),
    ]
    lines = reassemble_lines(spans)
    assert len(lines) == 2


def test_vertical_text_reassembles_top_to_bottom():
    spans = [
        span("4\"", 500, 100, 510, 115, direction=(0.0, -1.0)),
        span("3'-", 500, 115, 510, 130, direction=(0.0, -1.0)),
    ]
    lines = reassemble_lines(spans)
    assert len(lines) == 1
    assert lines[0].text == "3'-4\""
