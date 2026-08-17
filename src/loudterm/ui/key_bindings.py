from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent

from loudterm.config import AppConfig
from loudterm.speed import faster, slower


def make_key_bindings(app_config: AppConfig) -> KeyBindings:
    key_bindings = KeyBindings()

    @key_bindings.add("c-s")
    def _(_: KeyPressEvent) -> None:
        app_config.auto_save = not app_config.auto_save

    @key_bindings.add("c-p")
    def _(_: KeyPressEvent) -> None:
        app_config.auto_play = not app_config.auto_play

    @key_bindings.add("c-up")
    def _(_: KeyPressEvent) -> None:
        app_config.speed = faster(app_config.speed)

    @key_bindings.add("c-down")
    def _(_: KeyPressEvent) -> None:
        app_config.speed = slower(app_config.speed)

    return key_bindings
