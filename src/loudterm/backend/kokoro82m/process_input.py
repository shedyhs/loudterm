import asyncio
from concurrent.futures import ThreadPoolExecutor

from loudterm.audio.controls import PlaybackControls
from loudterm.backend.kokoro82m.generator import KokoroGenerator
from loudterm.backend.kokoro82m.pipeline import kokoro_blocking_pipeline
from loudterm.config import AppConfig
from loudterm.ui.playback_menu import run_playback_menu


async def kokoro_process_input(
    text: str,
    executor: ThreadPoolExecutor,
    app_config: AppConfig,
    kokoro_generator: KokoroGenerator,
) -> None:
    """
    Handles the user input in a separate thread to avoid blocking the event loop.

    While the worker speaks, the event loop shows the playback control menu so
    the user can pause, skip, stop or change speed without waiting for the end.
    """
    loop = asyncio.get_running_loop()
    controls = PlaybackControls()

    playback = loop.run_in_executor(
        executor,
        kokoro_blocking_pipeline,
        text,
        app_config,
        kokoro_generator,
        controls,
    )

    try:
        if app_config.auto_play:
            await run_playback_menu(controls, app_config, playback)
    finally:
        await playback
