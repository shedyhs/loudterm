from dataclasses import dataclass
from typing import Any, Literal

from loudterm.backend.kokoro82m.generator import KokoroGenerator
from loudterm.backend.kokoro82m.pipeline import load_kokoro_generator
from loudterm.backend.kokoro82m.voices import KOKORO_VOICES
from loudterm.config import AppConfig
from loudterm.speed import MAX_SPEED, MIN_SPEED, parse_speed_arg
from loudterm.ui.prints import print_dim, print_error, print_exit, print_success

SPEED_COMMAND = "/speed"


@dataclass(frozen=True, slots=True)
class LoopControl:
    loop_action: Literal["continue", "break", "pass"]
    data: Any


def _handle_speed_command(arg: str, app_config: AppConfig) -> LoopControl:
    new_speed = parse_speed_arg(arg, app_config.speed)

    if new_speed is None:
        print_error(
            f"Invalid speed. Use /speed 1.5, /speed +, /speed -0.2 or "
            f"/speed reset (range {MIN_SPEED}-{MAX_SPEED}).\n",
        )
        return LoopControl("continue", None)

    app_config.speed = new_speed
    print_dim(f"Speed set to {new_speed}x\n")
    return LoopControl("continue", None)


async def process_commands(
    text: str,
    app_config: AppConfig,
    kokoro_generator: KokoroGenerator,
) -> LoopControl:
    min_text_length = 10

    if not text:
        print_error("No text found\n")
        return LoopControl("continue", None)

    command = text.lower()

    if command in KOKORO_VOICES:
        language_data = KOKORO_VOICES[command]
        language_code = language_data["language_code"]
        description = language_data["desc"]

        print_dim(f"Voice changed to: {command[1:]}...")
        print_dim(f"Switching language to {description}...\n")

        app_config.voice = command[1:]
        app_config.lang = language_code

        try:
            new_generator = load_kokoro_generator(app_config)
            del kokoro_generator  # not necessary, only to ensure garbage collection
            kokoro_generator = new_generator

        except Exception as e:  # noqa: BLE001
            print_success(f"Error reloading engine: {e}\n")
        return LoopControl("continue", kokoro_generator)

    if command.startswith(SPEED_COMMAND):
        return _handle_speed_command(text[len(SPEED_COMMAND) :], app_config)

    if text.lower().strip() in ("/exit", "/quit", "/q", "/bye"):
        print_exit()
        return LoopControl("break", None)

    if len(text) < min_text_length:
        print_error(f"Try {min_text_length} chars or more...\n")
        return LoopControl("continue", None)

    return LoopControl("pass", None)
