import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import PipeInput, create_pipe_input
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.output import DummyOutput

from loudterm.audio.controls import PlaybackControls, PlaybackSnapshot
from loudterm.config import AppConfig
from loudterm.speed import faster, slower
from loudterm.ui.playback_menu import (
    BAR_WIDTH,
    format_seconds,
    make_menu_key_bindings,
    progress_bar,
    render_menu,
    run_playback_menu,
    status_label,
)

MENU_TIMEOUT = 5.0
SETTLE = 0.2

type Scenario = Callable[
    [PipeInput, PlaybackControls, AppConfig],
    Awaitable[None],
]


def make_snapshot(
    *,
    is_paused: bool = False,
    is_stopped: bool = False,
) -> PlaybackSnapshot:
    return PlaybackSnapshot(
        chunk=1,
        is_paused=is_paused,
        is_stopped=is_stopped,
        played_seconds=1.0,
        total_seconds=4.0,
    )


def press(key_bindings: KeyBindings, key: str | Keys) -> None:
    """Fire the handler bound to `key`, like a real key press would."""
    bindings = [b for b in key_bindings.bindings if key in b.keys]

    if not bindings:
        message = f"no binding registered for {key!r}"
        raise AssertionError(message)

    bindings[0].handler(cast("KeyPressEvent", None))


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0.0, "00:00"), (9.7, "00:09"), (65.0, "01:05"), (600.0, "10:00")],
)
def test_format_seconds_uses_minutes_and_seconds(seconds: float, expected: str):
    assert format_seconds(seconds) == expected


@pytest.mark.parametrize(
    ("progress", "filled"),
    [(0.0, 0), (0.5, BAR_WIDTH // 2), (1.0, BAR_WIDTH), (2.0, BAR_WIDTH), (-1.0, 0)],
)
def test_progress_bar_fills_proportionally(progress: float, filled: int):
    bar = progress_bar(progress)

    assert len(bar) == BAR_WIDTH
    assert bar.count("█") == filled


@pytest.mark.parametrize(
    ("snapshot", "expected"),
    [
        (make_snapshot(), "▶ Playing"),
        (make_snapshot(is_paused=True), "⏸ Paused"),
        (make_snapshot(is_stopped=True), "■ Stopped"),
    ],
)
def test_status_label_reflects_the_snapshot(
    snapshot: PlaybackSnapshot,
    expected: str,
):
    assert status_label(snapshot) == expected


def test_render_menu_shows_status_progress_and_hints():
    controls = PlaybackControls()
    controls.start_chunk(2)
    controls.set_source(total_frames=48000, sample_rate=24000)
    controls.set_frames_played(24000)

    text = "".join(fragment[1] for fragment in render_menu(controls, AppConfig()))

    assert "▶ Playing" in text
    assert "chunk 2" in text
    assert "00:01/00:02" in text
    assert "1.0x" in text
    assert "[space] pause" in text
    assert "[s] stop" in text


def test_space_toggles_pause():
    controls = PlaybackControls()
    key_bindings = make_menu_key_bindings(controls, AppConfig())

    press(key_bindings, " ")
    assert controls.is_paused is True

    press(key_bindings, " ")
    assert controls.is_paused is False


def test_n_skips_the_current_chunk():
    controls = PlaybackControls()

    press(make_menu_key_bindings(controls, AppConfig()), "n")

    assert controls.is_skipping is True


@pytest.mark.parametrize("key", ["s", "q", Keys.ControlC])
def test_stop_keys_cancel_the_session(key: str | Keys):
    controls = PlaybackControls()

    press(make_menu_key_bindings(controls, AppConfig()), key)

    assert controls.is_stopped is True


def test_arrow_keys_change_the_speed():
    app_config = AppConfig()
    key_bindings = make_menu_key_bindings(PlaybackControls(), app_config)
    start = app_config.speed

    press(key_bindings, Keys.Up)
    assert app_config.speed == faster(start)

    press(key_bindings, Keys.Down)
    assert app_config.speed == slower(faster(start))


def run_headless(scenario: Scenario) -> None:
    """Run `scenario(pipe_input, controls, app_config)` against a live menu app."""

    async def main() -> None:
        with (
            create_pipe_input() as pipe_input,
            create_app_session(
                input=pipe_input,
                output=DummyOutput(),
            ),
        ):
            controls = PlaybackControls()
            app_config = AppConfig()
            playback: asyncio.Future[None] = asyncio.get_running_loop().create_future()
            menu = asyncio.ensure_future(
                run_playback_menu(controls, app_config, playback),
            )

            await asyncio.sleep(SETTLE)
            await scenario(pipe_input, controls, app_config)

            if not playback.done():
                playback.set_result(None)

            await asyncio.wait_for(menu, timeout=MENU_TIMEOUT)

    asyncio.run(main())


def test_menu_closes_when_playback_finishes():
    async def scenario(
        _pipe_input: PipeInput,
        controls: PlaybackControls,
        _app_config: AppConfig,
    ) -> None:
        assert controls.is_stopped is False

    run_headless(scenario)


def test_menu_reacts_to_keys_while_running():
    async def scenario(
        pipe_input: PipeInput,
        controls: PlaybackControls,
        app_config: AppConfig,
    ) -> None:
        pipe_input.send_text(" ")
        await asyncio.sleep(SETTLE)
        assert controls.is_paused is True

        pipe_input.send_text("s")
        await asyncio.sleep(SETTLE)
        assert controls.is_stopped is True
        assert app_config.speed == 1.0

    run_headless(scenario)
