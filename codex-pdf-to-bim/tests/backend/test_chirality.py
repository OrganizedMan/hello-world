"""Handedness, asked of a mapping rather than of named furniture.

`matches_drawing` needs a sink, a range and an island, which is fine for the
kitchen and useless for a bedroom. `mapping_preserves_handedness` asks the same
question of the coordinate conversion itself, so every floor of the house can be
checked the same way.
"""

from __future__ import annotations

from hearthview.chirality import mapping_preserves_handedness


def test_a_north_positive_mapping_matches_the_drawing() -> None:
    """PDF y grows southward, so north-positive means negating it."""
    assert mapping_preserves_handedness(lambda x, y: (x, -y))


def test_measuring_south_instead_of_north_is_a_mirror() -> None:
    """The exact bug that shipped the kitchen reflected, twice."""
    assert not mapping_preserves_handedness(lambda x, y: (x, y))


def test_flipping_east_is_also_a_mirror() -> None:
    assert not mapping_preserves_handedness(lambda x, y: (-x, -y))


def test_offsets_and_scales_do_not_change_handedness() -> None:
    """Only the sign structure matters; a translated, scaled frame is fine."""
    assert mapping_preserves_handedness(lambda x, y: (3.5 * (x - 981.0), 3.5 * (622.0 - y)))


def test_flipping_both_axes_is_a_rotation_not_a_reflection() -> None:
    """Two reflections compose into a 180-degree turn, which is legal."""
    assert mapping_preserves_handedness(lambda x, y: (-x, y))
