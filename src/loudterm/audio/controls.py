"""Playback state shared between the audio worker thread and the control menu.

The pipeline generates and plays audio on a worker thread while the control menu
runs on the asyncio event loop, so both sides talk through this object. Every
access takes the same lock: the audio callback only reads a couple of flags per
block (~40ms at 24kHz), so contention is irrelevant next to the clarity of a
single guard.
"""

import threading
from dataclasses import dataclass

MIN_SAMPLE_RATE = 1


@dataclass(frozen=True, slots=True)
class PlaybackSnapshot:
    """Immutable view of the playback state, safe to render from the UI."""

    chunk: int
    is_paused: bool
    is_stopped: bool
    played_seconds: float
    total_seconds: float

    @property
    def progress(self) -> float:
        """Fraction of the current chunk already played, between 0 and 1."""
        if self.total_seconds <= 0:
            return 0.0
        return min(self.played_seconds / self.total_seconds, 1.0)


class PlaybackControls:
    """Thread-safe controls for an in-flight speech session."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._paused = False
        self._stopped = False
        self._skipping = False
        self._chunk = 0
        self._frames_played = 0
        self._total_frames = 0
        self._sample_rate = MIN_SAMPLE_RATE

    @property
    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    @property
    def is_stopped(self) -> bool:
        with self._lock:
            return self._stopped

    @property
    def is_skipping(self) -> bool:
        with self._lock:
            return self._skipping

    def pause(self) -> None:
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            self._paused = False

    def toggle_pause(self) -> None:
        with self._lock:
            self._paused = not self._paused

    def stop(self) -> None:
        """Cancel the whole session: current chunk and everything after it."""
        with self._lock:
            self._stopped = True
            self._paused = False

    def skip(self) -> None:
        """Abort the current chunk and move on to the next one."""
        with self._lock:
            self._skipping = True
            self._paused = False

    def consume_skip(self) -> None:
        """Clear the skip request once the player has honored it."""
        with self._lock:
            self._skipping = False

    def start_chunk(self, index: int) -> None:
        """Announce that chunk `index` is about to play, resetting its progress."""
        with self._lock:
            self._chunk = index
            self._skipping = False
            self._frames_played = 0
            self._total_frames = 0

    def set_source(self, total_frames: int, sample_rate: int) -> None:
        """Register the size of the buffer the player is about to stream."""
        with self._lock:
            self._total_frames = total_frames
            self._sample_rate = max(sample_rate, MIN_SAMPLE_RATE)

    def set_frames_played(self, frames: int) -> None:
        with self._lock:
            self._frames_played = frames

    def snapshot(self) -> PlaybackSnapshot:
        with self._lock:
            return PlaybackSnapshot(
                chunk=self._chunk,
                is_paused=self._paused,
                is_stopped=self._stopped,
                played_seconds=self._frames_played / self._sample_rate,
                total_seconds=self._total_frames / self._sample_rate,
            )
