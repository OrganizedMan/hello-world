from ingest import PageSignals, Tier, detect_tier


def signals(path=0, spans=0, image_frac=0.0):
    return PageSignals(
        page_index=0, width_pt=2592, height_pt=1728,
        vector_path_count=path, text_span_count=spans, image_area_fraction=image_frac,
    )


def test_structured_vector_is_tier_a():
    r = detect_tier(signals(path=9789, spans=209, image_frac=0.02))
    assert r.tier == Tier.A


def test_full_page_raster_with_no_vectors_is_tier_c():
    r = detect_tier(signals(path=0, spans=0, image_frac=1.0))
    assert r.tier == Tier.C


def test_sparse_vector_is_tier_b():
    r = detect_tier(signals(path=50, spans=10, image_frac=0.0))
    assert r.tier == Tier.B


def test_rich_vector_but_no_text_is_not_tier_a():
    # a lot of linework but nothing labelled — treat conservatively, not A
    r = detect_tier(signals(path=5000, spans=0, image_frac=0.0))
    assert r.tier == Tier.B


def test_large_photo_alongside_dense_vector_is_still_tier_a():
    # a legend photo or 3D thumbnail shouldn't push a genuinely vector,
    # richly-labelled sheet into Tier C
    r = detect_tier(signals(path=9789, spans=209, image_frac=0.3))
    assert r.tier == Tier.A


def test_every_tier_has_an_effort_estimate_string():
    for tier in Tier:
        r = detect_tier(signals(
            path=9789 if tier == Tier.A else (50 if tier == Tier.B else 0),
            spans=209 if tier == Tier.A else (10 if tier == Tier.B else 0),
            image_frac=1.0 if tier == Tier.C else 0.0,
        ))
        assert r.tier == tier
        assert r.effort_estimate
        assert "Tier" in str(r)
