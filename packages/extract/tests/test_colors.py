from extract.colors import (
    DEMOLITION_STROKE,
    EXISTING_WALL_FILL,
    NEW_WALL_FILL,
    TEXT_MASK_FILL,
    classify_fill,
    classify_stroke,
    color_close,
)


def test_known_fills_classify_correctly():
    assert classify_fill(EXISTING_WALL_FILL) == "existing_wall"
    assert classify_fill(NEW_WALL_FILL) == "new_wall"
    assert classify_fill(TEXT_MASK_FILL) == "text_mask"
    assert classify_fill((0.902, 0.902, 0.902)) == "casework"


def test_unknown_fill_is_unclassified_not_guessed():
    assert classify_fill((0.123, 0.456, 0.789)) is None
    assert classify_fill(None) is None


def test_known_strokes_classify_correctly():
    assert classify_stroke(DEMOLITION_STROKE) == "demolition_or_leader"
    assert classify_stroke((0.0, 0.0, 1.0)) == "dimension_or_clg_tag"


def test_color_close_has_tight_tolerance():
    assert color_close((0.851, 0.851, 0.851), EXISTING_WALL_FILL)
    assert not color_close((0.75, 0.75, 0.75), EXISTING_WALL_FILL)
    assert not color_close(None, EXISTING_WALL_FILL)
