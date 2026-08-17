import threading
from typing import Any

import numpy as np
import sounddevice as sd
from numpy.typing import NDArray
from torch import Tensor

from loudterm.audio.controls import PlaybackControls
from loudterm.core import AudioResult

CHANNELS = 1
BLOCK_SIZE = 1024


def to_frames(samples: Tensor) -> NDArray[np.float32]:
    """Convert Kokoro samples into the (frames, channels) layout sounddevice wants."""
    array: Any = samples.detach().cpu().numpy()  # type: ignore[reportUnknownMemberType]
    return np.asarray(array, dtype=np.float32).reshape(-1, CHANNELS)


class AudioPlayer:
    """High-level audio playback API using sounddevice."""

    def play(
        self,
        audio: AudioResult,
        controls: PlaybackControls | None = None,
    ) -> None:
        """Play audio blocking until finished.

        Without `controls` this is a plain blocking playback. With them, audio is
        streamed in small blocks so the control menu can pause, skip or stop it
        while it plays.
        """
        if controls is None:
            sd.play(audio.samples, audio.sample_rate, blocking=True)  # type: ignore[reportUnknownMemberType]
            return

        self._play_streaming(audio, controls)

    def _play_streaming(self, audio: AudioResult, controls: PlaybackControls) -> None:
        frames = to_frames(audio.samples)
        controls.set_source(total_frames=len(frames), sample_rate=audio.sample_rate)

        cursor = 0
        finished = threading.Event()

        def callback(
            outdata: NDArray[np.float32],
            block_size: int,
            _time: object,
            _status: object,
        ) -> None:
            nonlocal cursor

            if controls.is_stopped or controls.is_skipping:
                raise sd.CallbackAbort

            if controls.is_paused:
                outdata[:] = 0.0
                return

            block = frames[cursor : cursor + block_size]
            written = len(block)
            outdata[:written] = block
            cursor += written
            controls.set_frames_played(cursor)

            if written < block_size:
                outdata[written:] = 0.0
                raise sd.CallbackStop

        stream = sd.OutputStream(  # type: ignore[reportUnknownMemberType]
            samplerate=audio.sample_rate,
            channels=CHANNELS,
            dtype="float32",
            blocksize=BLOCK_SIZE,
            callback=callback,
            finished_callback=finished.set,
        )

        with stream:
            finished.wait()

        controls.consume_skip()
