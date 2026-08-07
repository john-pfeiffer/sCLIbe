"""Unit tests for the pure functions — no ffmpeg, no API."""

from shinescript.analyze import Step, StepList, sanitize
from shinescript.frames import plan_timestamps
from shinescript.video import chapter_spans, ffmetadata_escape, padded_ranges


def make_step(n, start, end, key=None):
    return Step(
        number=n, title=f"t{n}", description="d", narration="n",
        start_time=start, end_time=end, key_frame_time=key if key is not None else start,
    )


def test_sanitize_fixes_overlaps_and_snaps_keyframes():
    result = StepList(
        process_title="p", process_summary="s",
        steps=[make_step(2, 10.0, 25.0, key=11.0), make_step(1, 20.0, 40.0, key=33.3)],
    )
    out = sanitize(result, duration=60.0, frame_times=[12.0, 30.0])
    assert [s.number for s in out.steps] == [1, 2]
    assert out.steps[0].end_time == out.steps[1].start_time == 22.5  # midpoint split
    assert out.steps[0].key_frame_time == 12.0
    assert out.steps[1].key_frame_time == 30.0


def test_sanitize_clamps_to_duration():
    result = StepList(process_title="p", process_summary="s",
                      steps=[make_step(1, -5.0, 999.0)])
    out = sanitize(result, duration=60.0, frame_times=[10.0])
    assert out.steps[0].start_time == 0.0
    assert out.steps[0].end_time == 60.0


def test_plan_timestamps_caps_and_keeps_endpoints():
    candidates = [(float(t), 5.0) for t in range(5, 300, 3)]
    planned = plan_timestamps(candidates, duration=300.0, max_frames=20)
    assert len(planned) <= 20
    times = [t for t, _ in planned]
    assert min(times) <= 1.0          # first frame kept
    assert max(times) >= 298.0        # last frame kept


def test_plan_timestamps_backfills_long_gaps():
    # only one detection in a 2-minute video -> sparse fallback + backfill kick in
    planned = plan_timestamps([(5.0, 9.0)], duration=150.0, max_frames=60)
    times = [t for t, _ in planned]
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert max(gaps) <= 30.0


def test_chapter_spans_are_cumulative():
    assert chapter_spans([10.0, 5.5]) == [(0, 10000), (10000, 15500)]


def test_ffmetadata_escape():
    assert ffmetadata_escape("a=b;c#d\\e\nf") == "a\\=b\\;c\\#d\\\\e f"


def test_padded_ranges_never_overlap():
    steps = [
        {"number": 1, "start_time": 1.0, "end_time": 10.0},
        {"number": 2, "start_time": 10.1, "end_time": 20.0},
    ]
    ranges = padded_ranges(steps, duration=30.0)
    assert ranges[0][1] <= ranges[1][0]
    assert ranges[0][0] == 0.75  # 1.0 - 0.25 pad


def test_ffcolor_accepts_hash_and_bare_hex():
    from shinescript.style import ffcolor
    assert ffcolor("#2563EB") == "0x2563eb"
    assert ffcolor("ff0000") == "0xff0000"


def test_ffcolor_rejects_garbage():
    import pytest
    from shinescript.style import ffcolor
    for bad in ("blue", "#12345", "#12345g"):
        with pytest.raises(ValueError):
            ffcolor(bad)


def test_fit_fontsize_shrinks_for_long_titles():
    from shinescript.style import fit_fontsize
    short = fit_fontsize("Hi", 1280, 108)
    long = fit_fontsize("A Very Long Process Title That Goes On And On Forever", 1280, 108)
    assert short == 108
    assert 16 <= long < short


def test_merge_settings_precedence():
    from shinescript.config import DEFAULTS, merge_settings
    cli = {"accent": "#ff0000", "banners": False}          # explicit CLI values
    config = {"accent": "#00ff00", "font": "Georgia"}       # file values
    out = merge_settings(cli, config)
    assert out["accent"] == "#ff0000"     # CLI beats config
    assert out["font"] == "Georgia"       # config beats default
    assert out["banners"] is False        # CLI False is respected, not treated as unset
    assert out["model"] == DEFAULTS["model"]  # untouched keys fall through to defaults
