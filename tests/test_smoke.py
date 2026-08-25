"""Unit tests for the pure functions — no ffmpeg, no API."""

from sclibe.analyze import Step, StepList, sanitize
from sclibe.frames import plan_timestamps
from sclibe.video import chapter_spans, ffmetadata_escape, padded_ranges


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
    from sclibe.style import ffcolor
    assert ffcolor("#2563EB") == "0x2563eb"
    assert ffcolor("ff0000") == "0xff0000"


def test_ffcolor_rejects_garbage():
    import pytest
    from sclibe.style import ffcolor
    for bad in ("blue", "#12345", "#12345g"):
        with pytest.raises(ValueError):
            ffcolor(bad)


def test_fit_fontsize_shrinks_for_long_titles():
    from sclibe.style import fit_fontsize
    short = fit_fontsize("Hi", 1280, 108)
    long = fit_fontsize("A Very Long Process Title That Goes On And On Forever", 1280, 108)
    assert short == 108
    assert 16 <= long < short


def test_merge_settings_precedence():
    from sclibe.config import DEFAULTS, merge_settings
    cli = {"accent": "#ff0000", "banners": False}          # explicit CLI values
    config = {"accent": "#00ff00", "font": "Georgia"}       # file values
    out = merge_settings(cli, config)
    assert out["accent"] == "#ff0000"     # CLI beats config
    assert out["font"] == "Georgia"       # config beats default
    assert out["banners"] is False        # CLI False is respected, not treated as unset
    assert out["model"] == DEFAULTS["model"]  # untouched keys fall through to defaults


def test_clean_path_handles_drag_and_paste_forms():
    from sclibe.cli import clean_path
    assert str(clean_path("/tmp/My\\ Recording.mov ")) == "/tmp/My Recording.mov"
    assert str(clean_path("'/tmp/quoted path.mov'")) == "/tmp/quoted path.mov"
    assert str(clean_path('"/tmp/dq.mov"')) == "/tmp/dq.mov"
    assert str(clean_path("~/x.mov")).endswith("/x.mov") and "~" not in str(clean_path("~/x.mov"))


def test_stretch_plan_syncs_video_to_audio():
    from sclibe.narrate import stretch_plan
    assert stretch_plan(10.0, 8.0) == (1.0, 0.0)          # audio fits: no change
    f, fr = stretch_plan(10.0, 15.0)
    assert f == 1.5 and fr == 0.0                          # moderate: pure slow-mo
    f, fr = stretch_plan(4.0, 12.0)
    assert f == 2.0 and abs(fr - 4.0) < 1e-9               # extreme: capped + freeze


def test_sanitize_prefers_keyframe_inside_step_range():
    result = StepList(
        process_title="p", process_summary="s",
        steps=[make_step(1, 10.0, 20.0, key=52.0)],        # model picked a frame way outside
    )
    out = sanitize(result, duration=60.0, frame_times=[5.0, 15.0, 50.0])
    assert out.steps[0].key_frame_time == 15.0             # snapped to the in-range frame


def test_merge_settings_rejects_bad_tts():
    import pytest
    from sclibe.config import merge_settings
    with pytest.raises(ValueError):
        merge_settings({"tts": "siri"}, {})


def test_provider_for_maps_model_families():
    import pytest
    from sclibe.analyze import provider_for
    assert provider_for("claude-opus-5") == "anthropic"
    assert provider_for("claude-haiku-4-5") == "anthropic"
    assert provider_for("gpt-4o") == "openai"
    assert provider_for("o3-mini") == "openai"
    assert provider_for("grok-4") == "xai"
    with pytest.raises(ValueError):
        provider_for("llama-3")


def test_resolve_voice_expands_roster_names():
    from sclibe.config import merge_settings, resolve_voice
    config = {
        "voice": "brand",
        "voices": {"brand": {"tts": "elevenlabs", "voice": "UgBBYS2sOqTuMpoF3BR0"}},
    }
    merged = merge_settings({}, config)
    assert merged["voice"] == "brand"                  # file/state keeps the friendly name
    out = resolve_voice(merged)
    assert out["tts"] == "elevenlabs"                  # run time expands provider
    assert out["voice"] == "UgBBYS2sOqTuMpoF3BR0"      # and the real ID
    # a non-roster voice passes through untouched
    out2 = resolve_voice(merge_settings({"voice": "en-US-EmmaMultilingualNeural"}, config))
    assert out2["voice"] == "en-US-EmmaMultilingualNeural"


def test_materialized_config_is_complete():
    from sclibe.config import DEFAULTS, materialized
    full = materialized({"accent": "#0E7C5B"})
    assert set(full) == set(DEFAULTS)                  # every key present
    assert full["accent"] == "#0E7C5B"                 # overrides kept
    assert full["model"] == DEFAULTS["model"]          # gaps filled with defaults


def test_plan_timestamps_respects_min_gap():
    candidates = [(10.0, 5.0), (11.0, 6.0)]  # one second apart
    close = plan_timestamps(candidates, duration=60.0, max_frames=60, min_gap=0.5)
    assert {10.0, 11.0} <= {t for t, _ in close}       # both kept
    wide = plan_timestamps(candidates, duration=60.0, max_frames=60, min_gap=5.0)
    times = {t for t, _ in wide}
    assert 11.0 in times and 10.0 not in times          # merged, later one kept


def test_stretch_plan_custom_max_slowdown():
    from sclibe.narrate import stretch_plan
    assert stretch_plan(4.0, 12.0, max_slowdown=1.0) == (1.0, 8.0)  # never slow: hold only
    assert stretch_plan(4.0, 12.0, max_slowdown=3.0) == (3.0, 0.0)  # roomier cap: pure slow-mo


def test_card_seconds_fits_narration():
    from sclibe.narrate import card_seconds
    assert card_seconds(1.0) == 3.5                    # short narration: minimum card
    assert card_seconds(12.0) == 12.5                  # long narration: audio + tail


def test_title_card_mode_derivation():
    import pytest
    from sclibe.style import Style, title_card_mode
    assert title_card_mode(Style(title_card=False)) == "off"
    assert title_card_mode(Style()) == "text"
    assert title_card_mode(Style(title_card_image="logo.png")) == "image+text"
    assert title_card_mode(Style(title_card_image="logo.png", title_card_text=False)) == "image"
    with pytest.raises(ValueError):
        title_card_mode(Style(title_card_text=False))  # no image and no text
    assert title_card_mode(Style(title_card=False, title_card_text=False)) == "off"  # off wins


def test_merged_context_combines_flag_and_file():
    from sclibe.cli import merged_context
    assert merged_context("app demo", "# Details\nstuff") == "app demo\n\n# Details\nstuff"
    assert merged_context("app demo", None) == "app demo"
    assert merged_context(None, "# Details\n") == "# Details"
    assert merged_context(None, None) is None
    assert merged_context("", "  \n") is None          # blank inputs count as absent


def test_merge_settings_validates_timing_keys():
    import pytest
    from sclibe.config import merge_settings
    for bad in ({"settle_delay": -1.0}, {"min_gap": 0}, {"max_slowdown": 0.5}):
        with pytest.raises(ValueError):
            merge_settings(bad, {})
    out = merge_settings({"title_card_image": "/tmp/a.png"}, {"title_card_image": "/tmp/b.png"})
    assert out["title_card_image"] == "/tmp/a.png"     # CLI beats config for new keys too


def test_prompt_for_title_card_flow(tmp_path, monkeypatch):
    from sclibe.cli import prompt_for_title_card
    from sclibe.style import Style

    img = tmp_path / "logo.png"
    img.write_bytes(b"png")

    # yes to both: image (with one bad path retried) and a custom title
    answers = iter(["y", "/nope.png", str(img), "y", "Invoicing 101"])
    monkeypatch.setattr("builtins.input", lambda _="": next(answers))
    style = Style()
    prompt_for_title_card(style)
    assert style.title_card_image == str(img)
    assert style.title_text == "Invoicing 101"

    # no to both: AI defaults stay in place
    answers = iter(["n", "n"])
    style = Style()
    prompt_for_title_card(style)
    assert style.title_card_image is None and style.title_text is None

    # already configured image -> only the title question is asked
    answers = iter(["n"])
    style = Style(title_card_image=str(img))
    prompt_for_title_card(style)
    assert style.title_card_image == str(img)

    # image-only card configured -> nothing to ask at all
    answers = iter([])
    style = Style(title_card_image=str(img), title_card_text=False)
    prompt_for_title_card(style)


def test_stale_reason_detects_changes():
    from sclibe.cache import stale_reason
    fp = {"voice": "narrator", "tts": "elevenlabs"}
    assert stale_reason(fp, dict(fp), [100.0], [50.0]) is None            # clean cache
    assert stale_reason(None, fp, [100.0], [50.0]) is None                # pre-tracking: trust
    r = stale_reason({"voice": "old", "tts": "elevenlabs"}, fp, [100.0], [50.0])
    assert r == "settings changed (voice)"
    assert stale_reason(fp, dict(fp), [100.0], [200.0]) == "inputs changed"  # edited steps.json
    assert stale_reason(None, fp, [100.0], [200.0]) == "inputs changed"       # mtime wins even pre-tracking
