"""Interactive control menu shown while speech is playing.

The pipeline plays audio on a worker thread, so the event loop is free to run a
small prompt_toolkit application that captures keys and mutates the shared
`PlaybackControls`. The menu erases itself once playback ends.
"""

import asyncio
from contextlib import suppress

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.patch_stdout import patch_stdout

from loudterm.audio.controls import PlaybackControls, PlaybackSnapshot
from loudterm.config import AppConfig
from loudterm.speed import faster, slower
from loudterm.ui.styles import STYLES

BAR_WIDTH = 20
MENU_HEIGHT = 2
REFRESH_INTERVAL = 0.1
SECONDS_PER_MINUTE = 60

PRIMARY = STYLES.get_color("primary").hex
MUTED = STYLES.get_color("text_muted").hex
WARNING = STYLES.get_color("warning").hex
DANGER = STYLES.get_color("danger").hex

HINTS = (
    ("space", "pause"),
    ("n", "next chunk"),
    ("s", "stop"),
    ("↑/↓", "speed"),
)


def format_seconds(seconds: float) -> str:
    total = int(seconds)
    return f"{total // SECONDS_PER_MINUTE:02d}:{total % SECONDS_PER_MINUTE:02d}"


def progress_bar(progress: float, width: int = BAR_WIDTH) -> str:
    filled = round(min(max(progress, 0.0), 1.0) * width)
    return "█" * filled + "░" * (width - filled)


def status_label(snapshot: PlaybackSnapshot) -> str:
    if snapshot.is_stopped:
        return "■ Stopped"
    if snapshot.is_paused:
        return "⏸ Paused"
    return "▶ Playing"


def status_color(snapshot: PlaybackSnapshot) -> str:
    if snapshot.is_stopped:
        return DANGER
    if snapshot.is_paused:
        return WARNING
    return PRIMARY


def render_status(
    snapshot: PlaybackSnapshot,
    app_config: AppConfig,
) -> StyleAndTextTuples:
    color = status_color(snapshot)
    elapsed = format_seconds(snapshot.played_seconds)
    total = format_seconds(snapshot.total_seconds)

    return [
        (f"fg:{color} bold", f" {status_label(snapshot)} "),
        (f"fg:{MUTED}", f"chunk {snapshot.chunk} "),
        (f"fg:{color}", progress_bar(snapshot.progress)),
        (f"fg:{MUTED}", f" {elapsed}/{total} "),
        (f"fg:{MUTED}", "· "),
        (f"fg:{PRIMARY}", f"{app_config.speed}x "),
        (f"fg:{MUTED}", f"· @{app_config.voice}"),
    ]


def render_hints() -> StyleAndTextTuples:
    hints: StyleAndTextTuples = [(f"fg:{MUTED}", " ")]

    for key, action in HINTS:
        hints.append((f"fg:{PRIMARY}", f"[{key}]"))
        hints.append((f"fg:{MUTED}", f" {action}  "))

    return hints


def render_menu(
    controls: PlaybackControls,
    app_config: AppConfig,
) -> StyleAndTextTuples:
    snapshot = controls.snapshot()
    return [*render_status(snapshot, app_config), ("", "\n"), *render_hints()]


def make_menu_key_bindings(
    controls: PlaybackControls,
    app_config: AppConfig,
) -> KeyBindings:
    key_bindings = KeyBindings()

    @key_bindings.add(" ")
    @key_bindings.add("p")
    def _(_: KeyPressEvent) -> None:
        controls.toggle_pause()

    @key_bindings.add("n")
    def _(_: KeyPressEvent) -> None:
        controls.skip()

    @key_bindings.add("s")
    @key_bindings.add("q")
    @key_bindings.add("c-c")
    def _(_: KeyPressEvent) -> None:
        controls.stop()

    @key_bindings.add("up")
    @key_bindings.add("c-up")
    @key_bindings.add("+")
    def _(_: KeyPressEvent) -> None:
        app_config.speed = faster(app_config.speed)

    @key_bindings.add("down")
    @key_bindings.add("c-down")
    @key_bindings.add("-")
    def _(_: KeyPressEvent) -> None:
        app_config.speed = slower(app_config.speed)

    return key_bindings


def make_playback_app(
    controls: PlaybackControls,
    app_config: AppConfig,
) -> Application[None]:
    window = Window(
        content=FormattedTextControl(lambda: render_menu(controls, app_config)),
        height=MENU_HEIGHT,
        dont_extend_height=True,
    )

    return Application(
        layout=Layout(HSplit([window])),
        key_bindings=make_menu_key_bindings(controls, app_config),
        full_screen=False,
        erase_when_done=True,
        refresh_interval=REFRESH_INTERVAL,
    )


async def _exit_when_playback_ends(
    app: Application[None],
    playback: asyncio.Future[None],
    started: asyncio.Event,
) -> None:
    """Close the menu as soon as the worker thread is done with the speech."""
    with suppress(Exception):
        await asyncio.shield(playback)

    await started.wait()

    if app.is_running:
        app.exit()


async def run_playback_menu(
    controls: PlaybackControls,
    app_config: AppConfig,
    playback: asyncio.Future[None],
) -> None:
    """Show the control menu until `playback` finishes or the user stops it."""
    app = make_playback_app(controls, app_config)
    started = asyncio.Event()
    watcher = asyncio.ensure_future(_exit_when_playback_ends(app, playback, started))

    try:
        with patch_stdout(raw=True):
            await app.run_async(pre_run=started.set)
    finally:
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher
