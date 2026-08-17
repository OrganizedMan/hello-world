from __future__ import annotations

import pytest

from amber.config import SplitConfig
from amber.models import AmberError, EVAL, FrameRecord, TRAIN, UNUSED
from amber.pipeline import frames as frames_mod


def test_stratified_pick_is_deterministic(frames):
    first = [f.id for f in frames_mod.stratified_pick(frames, 8)]
    shuffled = list(reversed(frames))
    second = [f.id for f in frames_mod.stratified_pick(shuffled, 8)]
    assert first == second, "input order must not affect the frozen split"


def test_stratified_pick_spreads_across_the_whole_pool(frames):
    picked = frames_mod.stratified_pick(frames, 4)
    indices = [f.index for f in picked]

    assert len(picked) == 4
    assert indices == sorted(indices)
    assert indices[0] < 10 and indices[-1] > 29, "coverage must span the capture"


def test_stratified_pick_returns_everything_when_asked_for_too_many(frames):
    assert len(frames_mod.stratified_pick(frames, 999)) == len(frames)


def test_candidate_pool_hash_ignores_ordering(frames):
    assert frames_mod.candidate_pool_hash(frames) == frames_mod.candidate_pool_hash(
        list(reversed(frames))
    )


def test_candidate_pool_hash_changes_when_the_pool_changes(frames):
    baseline = frames_mod.candidate_pool_hash(frames)
    assert frames_mod.candidate_pool_hash(frames[:-1]) != baseline


def test_comparative_reservation_is_frozen_and_reproducible(frames):
    config = SplitConfig.comparative("group-a")
    first = frames_mod.reserve_fixed_evaluation(frames, config)
    second = frames_mod.reserve_fixed_evaluation(list(reversed(frames)), config)

    assert first.evaluation_frame_ids == second.evaluation_frame_ids
    assert first.candidate_pool_sha256 == second.candidate_pool_sha256
    assert first.comparison_group_id == "group-a"
    assert first.policy == "fixed_candidate_stratified"


def test_comparative_reservation_requires_a_group_id(frames):
    config = SplitConfig.comparative("g")
    bad = SplitConfig(
        policy=config.policy, n_eval=config.n_eval, comparison_group_id=None
    )
    with pytest.raises(AmberError, match="comparison_group_id"):
        frames_mod.reserve_fixed_evaluation(frames, bad)


def test_comparative_reservation_refuses_to_consume_the_whole_pool():
    small = [
        FrameRecord(id=f"f{i}", index=i, timestamp=i / 4.0, sharpness=1.0)
        for i in range(10)
    ]
    with pytest.raises(AmberError, match="nothing would remain"):
        frames_mod.reserve_fixed_evaluation(small, SplitConfig.comparative("g"))


def test_training_selection_never_includes_reserved_evaluation_frames(frames):
    config = SplitConfig.comparative("group-a")
    split = frames_mod.reserve_fixed_evaluation(frames, config)
    training = frames_mod.select_training_frames(frames, split, 6)

    assert set(f.id for f in training).isdisjoint(split.evaluation_frame_ids)


def test_evaluation_frames_are_pose_inputs_but_not_training_inputs(frames):
    config = SplitConfig.comparative("group-a")
    split = frames_mod.reserve_fixed_evaluation(frames, config)
    split.training_frame_ids = [
        f.id for f in frames_mod.select_training_frames(frames, split, 6)
    ]

    pose_inputs = frames_mod.pose_input_ids(split)

    assert set(split.evaluation_frame_ids).issubset(pose_inputs)
    assert set(split.evaluation_frame_ids).isdisjoint(split.training_frame_ids)
    assert len(pose_inputs) == len(set(pose_inputs)), "no duplicates"


def test_registered_interval_holds_out_every_eighth_frame():
    registered = [
        FrameRecord(id=f"f{i:03d}", index=i, timestamp=i / 4.0) for i in range(80)
    ]
    split = frames_mod.registered_interval_split(registered, SplitConfig.production())

    assert len(split.evaluation_frame_ids) == 10
    assert split.evaluation_frame_ids[0] == "f007"
    assert set(split.training_frame_ids).isdisjoint(split.evaluation_frame_ids)
    assert len(split.training_frame_ids) + len(split.evaluation_frame_ids) == 80


def test_small_captures_use_a_stratified_holdout_instead():
    registered = [
        FrameRecord(id=f"f{i:03d}", index=i, timestamp=i / 4.0) for i in range(20)
    ]
    split = frames_mod.registered_interval_split(registered, SplitConfig.production())

    assert len(split.evaluation_frame_ids) >= 4
    assert split.training_frame_ids, "a small capture must still leave training data"
    indices = [int(i[1:]) for i in split.evaluation_frame_ids]
    assert max(indices) - min(indices) > 10, "the holdout must span the capture"


def test_registered_interval_refuses_an_empty_input():
    with pytest.raises(AmberError, match="empty set"):
        frames_mod.registered_interval_split([], SplitConfig.production())


def test_apply_roles_marks_unused_frames(frames):
    split = frames_mod.reserve_fixed_evaluation(
        frames, SplitConfig.comparative("group-a")
    )
    split.training_frame_ids = [
        f.id for f in frames_mod.select_training_frames(frames, split, 4)
    ]
    frames_mod.apply_roles(frames, split)

    roles = {f.role for f in frames}
    assert roles == {TRAIN, EVAL, UNUSED}
    assert all(
        f.role == EVAL for f in frames if f.id in split.evaluation_frame_ids
    )


def test_eligibility_filters_blurred_frames_relative_to_the_median():
    from amber.config import CandidateConfig

    records = [
        FrameRecord(id=f"f{i}", index=i, timestamp=i / 4.0, sharpness=1.0)
        for i in range(9)
    ]
    records.append(
        FrameRecord(id="blurred", index=9, timestamp=2.25, sharpness=0.001)
    )
    for record in records:
        record.clipped_highlight_fraction = 0.0
        record.clipped_shadow_fraction = 0.0

    frames_mod.apply_eligibility(records, CandidateConfig.from_plan())

    assert records[-1].eligible is False
    assert records[-1].ineligible_reason == "motion_blur"
    assert all(r.eligible for r in records[:-1])
