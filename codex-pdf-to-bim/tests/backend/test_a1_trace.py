from hearthview.a1_trace import build_a1_trace


def test_trace_is_bound_to_the_proposed_a1_view() -> None:
    trace = build_a1_trace()

    assert trace.page_number == 2
    assert trace.page_width_points == 2592.0
    assert trace.page_height_points == 1728.24
    assert trace.proposed_crop.contains(trace.records[0].geometry.bounds)


def test_every_trace_record_has_one_explicit_provenance() -> None:
    records = build_a1_trace().records

    assert records
    assert {record.provenance for record in records} <= {
        "dimension_verified",
        "linework_traced",
        "ambiguous",
    }
    assert all(record.source_page == 2 for record in records)
