from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import torch

from loudterm.audio.controls import PlaybackControls
from loudterm.backend.kokoro82m import pipeline as pipeline_module
from loudterm.backend.kokoro82m.generator import KokoroGenerator
from loudterm.backend.kokoro82m.pipeline import kokoro_blocking_pipeline
from loudterm.config import AppConfig
from loudterm.core import AudioResult

CHUNK_FRAMES = 240
SAMPLE_RATE = 24000


class FakeGenerator:
    """Yields fixed chunks and records how many were actually pulled."""

    def __init__(self, chunks: int) -> None:
        self.chunks = chunks
        self.generated = 0

    def generate(self, **_: object) -> Generator[AudioResult]:
        for _index in range(self.chunks):
            self.generated += 1
            yield AudioResult(
                samples=torch.zeros(CHUNK_FRAMES),  # type: ignore[reportPrivateImportUsage]
                sample_rate=SAMPLE_RATE,
            )


class FakePlayer:
    """Records played chunks and can cancel the session mid-playback."""

    def __init__(self, stop_after: int | None = None) -> None:
        self.stop_after = stop_after
        self.played = 0

    def play(self, _audio: AudioResult, controls: PlaybackControls | None) -> None:
        self.played += 1
        if controls is not None and self.played == self.stop_after:
            controls.stop()


class FakeWriter:
    def __init__(self) -> None:
        self.saved: list[Path] = []

    def save(self, _audio: AudioResult, path: Path) -> None:
        self.saved.append(path)


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> tuple[FakePlayer, FakeWriter]:
    player = FakePlayer()
    writer = FakeWriter()
    monkeypatch.setattr(pipeline_module, "AudioPlayer", lambda: player)
    monkeypatch.setattr(pipeline_module, "AudioWriter", lambda: writer)
    return player, writer


def run_pipeline(
    generator: FakeGenerator,
    controls: PlaybackControls | None,
) -> None:
    kokoro_blocking_pipeline(
        "hello there",
        AppConfig(),
        # The pipeline only calls `generate`, so a stub is enough here
        generator,  # type: ignore[reportArgumentType]
        controls,
    )


def test_plays_every_chunk_and_saves_once(fakes: tuple[FakePlayer, FakeWriter]):
    player, writer = fakes
    generator = FakeGenerator(chunks=3)

    run_pipeline(generator, PlaybackControls())

    expected_chunks = 3
    assert player.played == expected_chunks
    assert len(writer.saved) == 1


def test_stopping_halts_generation_and_skips_saving(
    fakes: tuple[FakePlayer, FakeWriter],
):
    player, writer = fakes
    player.stop_after = 1
    generator = FakeGenerator(chunks=5)

    run_pipeline(generator, PlaybackControls())

    assert player.played == 1
    assert generator.generated == 1
    assert writer.saved == []


def test_runs_without_controls(fakes: tuple[FakePlayer, FakeWriter]):
    player, writer = fakes
    generator = FakeGenerator(chunks=2)

    run_pipeline(generator, None)

    expected_chunks = 2
    assert player.played == expected_chunks
    assert len(writer.saved) == 1


def test_generator_receives_a_live_speed_callable():
    captured: dict[str, Any] = {}

    class SpyGenerator(FakeGenerator):
        def generate(self, **kwargs: object) -> Generator[AudioResult]:
            captured.update(kwargs)
            return super().generate()

    app_config = AppConfig()
    kokoro_blocking_pipeline(
        "hello",
        app_config,
        SpyGenerator(chunks=0),  # type: ignore[reportArgumentType]
    )

    speed = captured["speed"]
    app_config.speed = 1.7
    assert speed(0) == app_config.speed


def test_generator_signature_accepts_a_speed_callable():
    annotations = KokoroGenerator.generate.__annotations__
    assert "Callable" in str(annotations["speed"])
