import os
from pathlib import Path


def cli_login_token_path() -> Path:
    """Path to the JWT file; must be a regular file (not a directory)."""
    override = (os.environ.get("ROKO_CONFIG_FILE") or "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".roko_config"


def save_cli_login_token(token: str) -> None:
    path = cli_login_token_path()
    if path.is_dir():
        raise RuntimeError(
            "CLI token path points to a directory (Docker often creates one if the host "
            "path was missing on first run). Fix on the host, then retry:\n"
            "  rm -rf ~/.roko_config .roko_config\n"
            "  touch ~/.roko_config          # local CLI\n"
            "  touch .roko_config            # Docker (project root, default compose bind)\n"
        )
    path.write_text(token.strip(), encoding="utf-8")
    path.chmod(0o600)


def load_cli_login_token() -> str | None:
    path = cli_login_token_path()
    if path.is_dir() or not path.is_file():
        return None
    t = path.read_text(encoding="utf-8").strip()
    return t or None
