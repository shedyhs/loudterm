import pytest

from loudterm.audio.controls import PlaybackControls, PlaybackSnapshot

SAMPLE_RATE = 24000


def make_controls(
    *,
    chunk: int = 1,
    total_frames: int = SAMPLE_RATE,
) -> PlaybackControls:
    controls = PlaybackControls()
    controls.start_chunk(chunk)
    controls.set_source(total_frames=total_frames, sample_rate=SAMPLE_RATE)
    return controls


def test_new_controls_start_playing():
    controls = PlaybackControls()

    assert controls.is_paused is False
    assert controls.is_stopped is False
    assert controls.is_skipping is False


def test_toggle_pause_flips_the_paused_flag():
    controls = PlaybackControls()

    controls.toggle_pause()
    assert controls.is_paused is True

    controls.toggle_pause()
    assert controls.is_paused is False


def test_pause_and_resume_are_explicit():
    controls = PlaybackControls()

    controls.pause()
    assert controls.is_paused is True

    controls.resume()
    assert controls.is_paused is False


def test_stop_also_releases_a_paused_playback():
    controls = PlaybackControls()
    controls.pause()

    controls.stop()

    assert controls.is_stopped is True
    assert controls.is_paused is False


def test_skip_also_releases_a_paused_playback():
    controls = PlaybackControls()
    controls.pause()

    controls.skip()

    assert controls.is_skipping is True
    assert controls.is_paused is False


def test_consume_skip_clears_the_request():
    controls = PlaybackControls()
    controls.skip()

    controls.consume_skip()

    assert controls.is_skipping is False


def test_start_chunk_resets_progress_and_pending_skip():
    controls = make_controls()
    controls.set_frames_played(SAMPLE_RATE // 2)
    controls.skip()

    controls.start_chunk(2)
    snapshot = controls.snapshot()

    expected_chunk = 2
    assert controls.is_skipping is False
    assert snapshot.chunk == expected_chunk
    assert snapshot.played_seconds == 0.0
    assert snapshot.total_seconds == 0.0


def test_start_chunk_keeps_a_stop_request():
    controls = make_controls()
    controls.stop()

    controls.start_chunk(2)

    assert controls.is_stopped is True


def test_snapshot_converts_frames_into_seconds():
    controls = make_controls(total_frames=SAMPLE_RATE * 4)
    controls.set_frames_played(SAMPLE_RATE)

    snapshot = controls.snapshot()

    expected_total = 4.0
    expected_progress = 0.25
    assert snapshot.played_seconds == 1.0
    assert snapshot.total_seconds == expected_total
    assert snapshot.progress == expected_progress


def test_snapshot_is_immutable():
    snapshot = make_controls().snapshot()

    with pytest.raises(AttributeError):
        snapshot.chunk = 99  # type: ignore[misc]


@pytest.mark.parametrize(
    ("played", "total", "expected"),
    [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (5.0, 4.0, 1.0),
        (2.0, 4.0, 0.5),
    ],
)
def test_progress_stays_between_zero_and_one(
    played: float,
    total: float,
    expected: float,
):
    snapshot = PlaybackSnapshot(
        chunk=1,
        is_paused=False,
        is_stopped=False,
        played_seconds=played,
        total_seconds=total,
    )

    assert snapshot.progress == expected
