"""Ports for the domain layer.

The domain may need to signal back to the host (CLI or web) that it requires
input. It does so by raising WebInputInterrupt — the host catches it and
prompts the user, then re-runs the operation with `manual_value` set.

This module has no dependencies outside the standard library, so it is safe
to import from any layer.
"""


class WebInputInterrupt(Exception):
    """Raised by domain code when interactive input is required.

    The host (CLI or web) catches it, collects input, then retries the
    operation with `manual_value=<text>`.
    """

    def __init__(self, prompt: str, type: str = "text", options: dict | None = None):
        super().__init__(prompt)
        self.prompt = prompt
        self.type = type
        self.options = options or {}


class _NullUI:
    """Default UI used when no host has registered one. Stays silent and
    flags web_mode so domain raises WebInputInterrupt instead of calling
    input()."""

    web_mode = True
    web_buffer: list = []

    def log_web(self, msg):
        self.web_buffer.append(msg)


ui = _NullUI()
