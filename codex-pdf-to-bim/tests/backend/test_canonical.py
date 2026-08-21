import pytest

from hearthview.canonical import CanonicalValueError, canonical_bytes, canonical_hash


def test_canonical_bytes_sort_mapping_keys_but_keep_list_order() -> None:
    first = {"walls": ["east", "south"], "project": {"name": "Garrigan", "revision": 2}}
    second = {"project": {"revision": 2, "name": "Garrigan"}, "walls": ["east", "south"]}

    assert canonical_bytes(first) == canonical_bytes(second)
    assert canonical_bytes(first) == (
        b'{"project":{"name":"Garrigan","revision":2},"walls":["east","south"]}'
    )


def test_canonical_bytes_reject_floats_before_they_enter_model_identity() -> None:
    with pytest.raises(CanonicalValueError, match="floating-point"):
        canonical_bytes({"width": 60.0})


def test_canonical_hash_is_stable_sha256() -> None:
    assert canonical_hash({"ticks": "61440"}) == (
        "0c7a6d11e0b752734192c481c4aa7c462c2f23a76addcd9e34098195aa899e65"
    )
