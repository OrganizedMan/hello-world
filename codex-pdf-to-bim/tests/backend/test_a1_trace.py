from hearthview.a1_trace import build_a1_trace, trace_summary


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


def test_trace_covers_each_required_proposed_plan_group() -> None:
    rooms = {record.room for record in build_a1_trace().records}

    assert {
        "kitchen",
        "living_room",
        "mudroom",
        "study_room",
        "existing_living_room",
        "powder_room",
        "walk_in_pantry",
        "staircase",
        "entry",
        "dining_room",
        "deck",
    } <= rooms


def test_trace_has_closed_exterior_boundary_and_wall_attached_openings() -> None:
    trace = build_a1_trace()

    assert trace.exterior_boundary.closed
    assert all(trace.attaches_to_wall(opening) for opening in trace.openings)


def test_dimension_verified_records_cite_printed_a1_labels() -> None:
    verified = [
        record
        for record in build_a1_trace().records
        if record.provenance == "dimension_verified"
    ]

    assert verified
    assert all(record.dimension_labels for record in verified)


def test_trace_summary_counts_each_provenance_state() -> None:
    summary = trace_summary(build_a1_trace())

    assert summary.verified > 0
    assert summary.traced > 0
    assert summary.ambiguous == 0
    assert summary.verified + summary.traced + summary.ambiguous == len(build_a1_trace().records)
